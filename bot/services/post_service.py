from __future__ import annotations

import asyncio
import logging
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
)
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.models import Post
from bot.storage import PostRepository, UserRepository
from bot.utils import deserialize_entities, serialize_entities, should_notify_document_update


class UnsupportedPostContentError(ValueError):
    pass


@dataclass(frozen=True)
class PostRender:
    content_type: str
    text: str | None = None
    entities: list | None = None
    file_id: str | None = None
    caption: str | None = None
    caption_entities: list | None = None


@dataclass
class DraftApplyResult:
    post: Post
    notice: str | None = None


logger = logging.getLogger(__name__)


class PostService:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        post_repository: PostRepository,
    ) -> None:
        self._session_maker = session_maker
        self._post_repository = post_repository

    def _empty_payload(self) -> dict[str, Any]:
        return {
            "main_text": None,
            "main_entities": None,
            "main_media": None,
            "extra_document": None,
        }

    def _load_payload(self, post: Post) -> dict[str, Any]:
        payload = deepcopy(post.entities) if isinstance(post.entities, dict) else None
        if not payload:
            payload = self._empty_payload()
        for key in ("main_text", "main_entities", "main_media", "extra_document"):
            payload.setdefault(key, None)
        return payload

    def _payload_flags(self, payload: dict[str, Any]) -> tuple[bool, bool, bool]:
        return (
            bool(payload.get("main_text")),
            bool(payload.get("main_media")),
            bool(payload.get("extra_document")),
        )

    async def _get_or_create_draft(self, admin_id: int) -> Post:
        async with self._session_maker() as session:
            async with session.begin():
                draft = await self._post_repository.get_active_draft_by_admin(session, admin_id)
                if draft:
                    return draft
                draft = await self._post_repository.create_draft(
                    session,
                    created_by=admin_id,
                    content_type="draft_v2",
                    text=None,
                    entities=self._empty_payload(),
                    file_id=None,
                    caption=None,
                    caption_entities=None,
                )
                await session.flush()
                return draft

    async def ensure_draft(self, admin_id: int) -> Post:
        return await self._get_or_create_draft(admin_id)

    async def clear_draft(self, admin_id: int) -> None:
        async with self._session_maker() as session:
            async with session.begin():
                draft = await self._post_repository.get_active_draft_by_admin(session, admin_id)
                if not draft:
                    return
                draft.entities = self._empty_payload()
                draft.content_type = "draft_v2"
                session.add(draft)

    async def cancel_draft(self, admin_id: int) -> None:
        async with self._session_maker() as session:
            async with session.begin():
                draft = await self._post_repository.get_active_draft_by_admin(session, admin_id)
                if not draft:
                    return
                await self._post_repository.mark_canceled(session, draft.id)

    async def apply_message_to_draft(self, admin_id: int, message: Message) -> DraftApplyResult:
        if message.media_group_id:
            raise UnsupportedPostContentError("album")

        notice: str | None = None
        saved_post: Post | None = None
        async with self._session_maker() as session:
            async with session.begin():
                draft = await self._post_repository.get_active_draft_by_admin(session, admin_id)
                if not draft:
                    draft = await self._post_repository.create_draft(
                        session,
                        created_by=admin_id,
                        content_type="draft_v2",
                        text=None,
                        entities=self._empty_payload(),
                        file_id=None,
                        caption=None,
                        caption_entities=None,
                    )
                    await session.flush()

                payload = self._load_payload(draft)

                if message.text:
                    payload["main_text"] = message.text
                    payload["main_entities"] = serialize_entities(message.entities)
                    update_type = "text"
                elif message.photo or message.video or message.animation:
                    media_type = "photo"
                    file_id = ""
                    if message.photo:
                        file_id = message.photo[-1].file_id
                    elif message.video:
                        media_type = "video"
                        file_id = message.video.file_id
                    elif message.animation:
                        media_type = "animation"
                        file_id = message.animation.file_id
                    payload["main_media"] = {
                        "type": media_type,
                        "file_id": file_id,
                        "caption": message.caption,
                        "caption_entities": serialize_entities(message.caption_entities),
                    }
                    notice = "Медиа обновлено." if payload.get("main_media") else None
                    update_type = f"media:{media_type}"
                elif message.document:
                    payload["extra_document"] = {
                        "file_id": message.document.file_id,
                        "file_name": message.document.file_name,
                        "caption": message.caption,
                        "caption_entities": serialize_entities(message.caption_entities),
                    }
                    if message.chat and message.from_user and should_notify_document_update(
                        chat_id=message.chat.id,
                        user_id=message.from_user.id,
                    ):
                        notice = "Файл заменён. Он будет отправлен отдельным сообщением."
                    update_type = "document"
                else:
                    raise UnsupportedPostContentError("unsupported")

                draft.entities = payload
                draft.content_type = "draft_v2"
                session.add(draft)
                await session.flush()
                has_text, has_media, has_doc = self._payload_flags(payload)
                logger.info(
                    "Post draft updated admin_id=%s type=%s has_text=%s has_media=%s has_doc=%s",
                    admin_id,
                    update_type,
                    has_text,
                    has_media,
                    has_doc,
                )
                saved_post = draft

        read_back = await self.get_active_draft(admin_id)
        if read_back:
            read_payload = self._load_payload(read_back)
            has_text, has_media, has_doc = self._payload_flags(read_payload)
            logger.info(
                "Post draft write-read check admin_id=%s has_text=%s has_media=%s has_doc=%s",
                admin_id,
                has_text,
                has_media,
                has_doc,
            )
        else:
            logger.warning("Post draft write-read check failed admin_id=%s draft_not_found", admin_id)
        return DraftApplyResult(post=read_back or saved_post, notice=notice)

    async def get_active_draft(self, admin_id: int) -> Post | None:
        async with self._session_maker() as session:
            draft = await self._post_repository.get_active_draft_by_admin(session, admin_id)
            logger.info("Post draft fetched admin_id=%s found=%s", admin_id, bool(draft))
            return draft

    def _resolve_main(self, post: Post) -> dict[str, Any]:
        payload = self._load_payload(post)
        media = payload.get("main_media")
        main_text = payload.get("main_text")
        main_entities = deserialize_entities(payload.get("main_entities"))
        if media:
            caption = media.get("caption")
            caption_entities = deserialize_entities(media.get("caption_entities"))
            if not caption and main_text:
                caption = main_text
                caption_entities = main_entities
            return {
                "type": media.get("type"),
                "file_id": media.get("file_id"),
                "caption": caption,
                "caption_entities": caption_entities,
            }
        if main_text:
            return {
                "type": "text",
                "text": main_text,
                "entities": main_entities,
            }
        return {"type": None}

    def _resolve_document(self, post: Post) -> dict[str, Any] | None:
        payload = self._load_payload(post)
        document = payload.get("extra_document")
        if not document:
            return None
        return {
            "file_id": document.get("file_id"),
            "file_name": document.get("file_name"),
            "caption": document.get("caption"),
            "caption_entities": deserialize_entities(document.get("caption_entities")),
        }

    def is_draft_empty(self, post: Post) -> bool:
        payload = self._load_payload(post)
        return not any(
            [payload.get("main_text"), payload.get("main_media"), payload.get("extra_document")]
        )

    async def send_preview(self, bot: Bot, chat_id: int, post: Post) -> None:
        main = self._resolve_main(post)
        document = self._resolve_document(post)
        if main.get("type") == "photo":
            await bot.send_photo(
                chat_id=chat_id,
                photo=main["file_id"],
                caption=main.get("caption"),
                caption_entities=main.get("caption_entities"),
            )
        elif main.get("type") == "video":
            await bot.send_video(
                chat_id=chat_id,
                video=main["file_id"],
                caption=main.get("caption"),
                caption_entities=main.get("caption_entities"),
            )
        elif main.get("type") == "animation":
            await bot.send_animation(
                chat_id=chat_id,
                animation=main["file_id"],
                caption=main.get("caption"),
                caption_entities=main.get("caption_entities"),
            )
        elif main.get("type") == "text":
            await bot.send_message(
                chat_id=chat_id,
                text=main.get("text") or "",
                entities=main.get("entities"),
            )

        if document:
            try:
                await bot.send_document(
                    chat_id=chat_id,
                    document=document["file_id"],
                    caption=document.get("caption"),
                    caption_entities=document.get("caption_entities"),
                )
            except TelegramBadRequest:
                name = document.get("file_name") or "без названия"
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"📎 Файл будет отправлен отдельным сообщением: {name}",
                )

    async def send_post_to_chat(self, bot: Bot, chat_id: int, post: Post) -> None:
        main = self._resolve_main(post)
        document = self._resolve_document(post)
        if main.get("type") == "photo":
            await bot.send_photo(
                chat_id=chat_id,
                photo=main["file_id"],
                caption=main.get("caption"),
                caption_entities=main.get("caption_entities"),
            )
        elif main.get("type") == "video":
            await bot.send_video(
                chat_id=chat_id,
                video=main["file_id"],
                caption=main.get("caption"),
                caption_entities=main.get("caption_entities"),
            )
        elif main.get("type") == "animation":
            await bot.send_animation(
                chat_id=chat_id,
                animation=main["file_id"],
                caption=main.get("caption"),
                caption_entities=main.get("caption_entities"),
            )
        elif main.get("type") == "text":
            await bot.send_message(
                chat_id=chat_id,
                text=main.get("text") or "",
                entities=main.get("entities"),
            )

        if document:
            await bot.send_document(
                chat_id=chat_id,
                document=document["file_id"],
                caption=document.get("caption"),
                caption_entities=document.get("caption_entities"),
            )

    async def broadcast_draft(
        self,
        bot: Bot,
        post: Post,
        *,
        user_repository: UserRepository,
        send_delay_seconds: float,
        batch_log_every: int,
    ) -> tuple[int, int]:
        async with self._session_maker() as session:
            user_ids = await user_repository.list_confirmed_user_ids(session)

        success_count = 0
        fail_count = 0
        total = len(user_ids)
        logger.info("Broadcast started: post_id=%s recipients=%s", post.id, total)

        for index, tg_id in enumerate(user_ids, start=1):
            try:
                await self._send_with_retry(bot, tg_id, post, send_delay_seconds)
                success_count += 1
            except (TelegramForbiddenError, TelegramNotFound, TelegramBadRequest, TelegramNetworkError):
                fail_count += 1
            if batch_log_every > 0 and index % batch_log_every == 0:
                logger.info("Broadcast progress: post_id=%s sent=%s/%s", post.id, index, total)
            if send_delay_seconds > 0:
                await asyncio.sleep(send_delay_seconds)

        async with self._session_maker() as session:
            async with session.begin():
                await self._post_repository.mark_sent(
                    session,
                    post.id,
                    sent_at=datetime.utcnow(),
                    success_count=success_count,
                    fail_count=fail_count,
                )
        logger.info(
            "Broadcast finished: post_id=%s success=%s failed=%s",
            post.id,
            success_count,
            fail_count,
        )
        return success_count, fail_count

    async def _send_with_retry(
        self, bot: Bot, tg_id: int, post: Post, send_delay_seconds: float
    ) -> None:
        attempts = 0
        while True:
            try:
                await self.send_post_to_chat(bot, tg_id, post)
                return
            except TelegramRetryAfter as exc:
                attempts += 1
                if attempts > 2:
                    raise
                retry_after = max(float(exc.retry_after), send_delay_seconds)
                await asyncio.sleep(retry_after)
            except TelegramNetworkError:
                attempts += 1
                if attempts > 2:
                    raise
                await asyncio.sleep(send_delay_seconds or 0.1)

    # Backward compatibility for other modules.
    async def create_draft_from_message(self, admin_id: int, message: Message) -> Post:
        result = await self.apply_message_to_draft(admin_id, message)
        return result.post

    def render_post(self, post: Post) -> PostRender:
        main = self._resolve_main(post)
        if main.get("type") in {"photo", "video", "animation"}:
            return PostRender(
                content_type=main["type"],
                file_id=main.get("file_id"),
                caption=main.get("caption") or "",
                caption_entities=main.get("caption_entities"),
            )
        return PostRender(
            content_type="text",
            text=main.get("text") or "",
            entities=main.get("entities"),
        )

    async def render_post_to_chat(
        self,
        bot: Bot,
        chat_id: int,
        post: Post,
        reply_markup=None,
    ) -> Message:
        main = self._resolve_main(post)
        if main.get("type") == "photo":
            return await bot.send_photo(
                chat_id=chat_id,
                photo=main["file_id"],
                caption=main.get("caption"),
                caption_entities=main.get("caption_entities"),
                reply_markup=reply_markup,
            )
        if main.get("type") == "video":
            return await bot.send_video(
                chat_id=chat_id,
                video=main["file_id"],
                caption=main.get("caption"),
                caption_entities=main.get("caption_entities"),
                reply_markup=reply_markup,
            )
        if main.get("type") == "animation":
            return await bot.send_animation(
                chat_id=chat_id,
                animation=main["file_id"],
                caption=main.get("caption"),
                caption_entities=main.get("caption_entities"),
                reply_markup=reply_markup,
            )
        return await bot.send_message(
            chat_id=chat_id,
            text=main.get("text") or "",
            entities=main.get("entities"),
            reply_markup=reply_markup,
        )

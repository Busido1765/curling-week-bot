from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.models import Post
from bot.storage import PostRepository
from bot.utils import deserialize_entities, serialize_entities


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


class PostService:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        post_repository: PostRepository,
    ) -> None:
        self._session_maker = session_maker
        self._post_repository = post_repository

    async def create_draft_from_message(self, admin_id: int, message: Message) -> Post:
        if message.text:
            content_type = "text"
            text = message.text
            entities = serialize_entities(message.entities)
            file_id = None
            caption = None
            caption_entities = None
        elif message.photo:
            content_type = "photo"
            text = None
            entities = None
            file_id = message.photo[-1].file_id
            caption = message.caption or ""
            caption_entities = serialize_entities(message.caption_entities)
        elif message.document:
            content_type = "document"
            text = None
            entities = None
            file_id = message.document.file_id
            caption = message.caption or ""
            caption_entities = serialize_entities(message.caption_entities)
        else:
            raise UnsupportedPostContentError("поддерживается text/photo/document")

        async with self._session_maker() as session:
            async with session.begin():
                post = await self._post_repository.create_draft(
                    session,
                    created_by=admin_id,
                    content_type=content_type,
                    text=text,
                    entities=entities,
                    file_id=file_id,
                    caption=caption,
                    caption_entities=caption_entities,
                )
                await session.flush()
                return post

    def render_post(self, post: Post) -> PostRender:
        if post.content_type == "photo" and post.file_id:
            return PostRender(
                content_type="photo",
                file_id=post.file_id,
                caption=post.caption or "",
                caption_entities=deserialize_entities(post.caption_entities),
            )
        if post.content_type == "document" and post.file_id:
            return PostRender(
                content_type="document",
                file_id=post.file_id,
                caption=post.caption or "",
                caption_entities=deserialize_entities(post.caption_entities),
            )
        return PostRender(
            content_type="text",
            text=post.text or "",
            entities=deserialize_entities(post.entities),
        )

    async def render_post_to_chat(
        self,
        bot: Bot,
        chat_id: int,
        post: Post,
        reply_markup=None,
    ) -> Message:
        render = self.render_post(post)
        if render.content_type == "photo" and render.file_id:
            return await bot.send_photo(
                chat_id=chat_id,
                photo=render.file_id,
                caption=render.caption,
                caption_entities=render.caption_entities,
                reply_markup=reply_markup,
            )
        if render.content_type == "document" and render.file_id:
            return await bot.send_document(
                chat_id=chat_id,
                document=render.file_id,
                caption=render.caption,
                caption_entities=render.caption_entities,
                reply_markup=reply_markup,
            )
        return await bot.send_message(
            chat_id=chat_id,
            text=render.text or "",
            entities=render.entities,
            reply_markup=reply_markup,
        )

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.storage import PostRepository, UserRepository
from bot.models import Post
from bot.services.post_service import PostService

logger = logging.getLogger(__name__)


class BroadcastService:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        post_repository: PostRepository,
        user_repository: UserRepository,
        post_service: PostService,
        *,
        send_delay_seconds: float,
        batch_log_every: int,
    ) -> None:
        self._session_maker = session_maker
        self._post_repository = post_repository
        self._user_repository = user_repository
        self._post_service = post_service
        self._send_delay_seconds = send_delay_seconds
        self._batch_log_every = batch_log_every

    async def broadcast_post(self, bot: Bot, post_id: int) -> tuple[int, int]:
        async with self._session_maker() as session:
            post = await self._post_repository.get(session, post_id)
            if post is None:
                raise ValueError("post not found")
            if post.status != "draft":
                raise ValueError("post already processed")
            user_ids = await self._user_repository.list_confirmed_user_ids(session)

        total = len(user_ids)
        success_count = 0
        fail_count = 0
        logger.info("Broadcast started: post_id=%s recipients=%s", post_id, total)

        for index, tg_id in enumerate(user_ids, start=1):
            try:
                await self._send_with_retry(bot, tg_id, post)
                success_count += 1
            except (TelegramForbiddenError, TelegramNotFound) as exc:
                fail_count += 1
                logger.warning("Broadcast blocked: tg_id=%s error=%s", tg_id, exc)
            except TelegramBadRequest as exc:
                fail_count += 1
                logger.warning("Broadcast bad request: tg_id=%s error=%s", tg_id, exc)
            except TelegramRetryAfter as exc:
                fail_count += 1
                logger.warning("Broadcast retry exhausted: tg_id=%s error=%s", tg_id, exc)
            except TelegramNetworkError as exc:
                fail_count += 1
                logger.error("Broadcast network error: tg_id=%s error=%s", tg_id, exc)
            if self._batch_log_every > 0 and index % self._batch_log_every == 0:
                logger.info(
                    "Broadcast progress: post_id=%s sent=%s/%s",
                    post_id,
                    index,
                    total,
                )
            if self._send_delay_seconds > 0:
                await asyncio.sleep(self._send_delay_seconds)

        async with self._session_maker() as session:
            async with session.begin():
                await self._post_repository.mark_sent(
                    session,
                    post_id,
                    sent_at=datetime.utcnow(),
                    success_count=success_count,
                    fail_count=fail_count,
                )

        logger.info(
            "Broadcast finished: post_id=%s success=%s failed=%s",
            post_id,
            success_count,
            fail_count,
        )
        return success_count, fail_count

    async def _send_with_retry(self, bot: Bot, tg_id: int, post: Post) -> None:
        attempts = 0
        while True:
            try:
                await self._post_service.render_post_to_chat(bot, tg_id, post)
                return
            except TelegramRetryAfter as exc:
                attempts += 1
                if attempts > 2:
                    raise
                retry_after = max(float(exc.retry_after), self._send_delay_seconds)
                logger.warning("Retry after %s seconds for tg_id=%s", retry_after, tg_id)
                await asyncio.sleep(retry_after)
            except TelegramNetworkError:
                attempts += 1
                if attempts > 2:
                    raise
                await asyncio.sleep(self._send_delay_seconds or 0.1)

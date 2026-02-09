from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Post


class PostRepository:
    async def create_draft(
        self,
        session: AsyncSession,
        *,
        created_by: int,
        content_type: str,
        text: str | None,
        entities: list[dict] | None,
        file_id: str | None,
        caption: str | None,
        caption_entities: list[dict] | None,
    ) -> Post:
        await session.execute(
            update(Post)
            .where(Post.created_by == created_by, Post.status == "draft")
            .values(status="canceled", sent_at=datetime.utcnow())
        )
        post = Post(
            created_by=created_by,
            content_type=content_type,
            text=text,
            entities=entities,
            file_id=file_id,
            caption=caption,
            caption_entities=caption_entities,
            status="draft",
        )
        session.add(post)
        return post

    async def get(self, session: AsyncSession, post_id: int) -> Post | None:
        result = await session.execute(select(Post).where(Post.id == post_id))
        return result.scalar_one_or_none()

    async def mark_sent(
        self,
        session: AsyncSession,
        post_id: int,
        *,
        sent_at: datetime,
        success_count: int,
        fail_count: int,
    ) -> None:
        await session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(
                status="sent",
                sent_at=sent_at,
                sent_count_success=success_count,
                sent_count_failed=fail_count,
            )
        )

    async def mark_canceled(self, session: AsyncSession, post_id: int) -> None:
        await session.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(status="canceled", sent_at=datetime.utcnow())
        )

    async def list_recent(self, session: AsyncSession, limit: int = 20) -> list[Post]:
        result = await session.execute(
            select(Post).order_by(Post.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

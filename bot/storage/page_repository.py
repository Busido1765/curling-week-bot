from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Page


class PageRepository:
    async def get_by_key(self, session: AsyncSession, key: str) -> Page | None:
        result = await session.execute(select(Page).where(Page.key == key))
        return result.scalar_one_or_none()

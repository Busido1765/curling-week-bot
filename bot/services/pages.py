from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.storage import PageRepository

PAGE_KEY_FAQ = "faq"
PAGE_KEY_CONTACTS = "contacts"
PAGE_KEY_SCHEDULE = "schedule"
PAGE_KEY_PHOTO = "photo"

DEFAULT_PAGE_MESSAGE = "Эта страница пока не настроена."


@dataclass(frozen=True)
class PageResult:
    key: str
    content: str | None


class PageService:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        page_repository: PageRepository,
    ) -> None:
        self._session_maker = session_maker
        self._page_repository = page_repository

    async def get_page(self, key: str) -> PageResult:
        async with self._session_maker() as session:
            page = await self._page_repository.get_by_key(session, key)
            if page is None:
                return PageResult(key=key, content=None)

            content = page.content.strip()
            if not content:
                return PageResult(key=key, content=None)

            return PageResult(key=key, content=page.content)

    async def update_page(self, key: str, content: str) -> PageResult:
        async with self._session_maker() as session:
            async with session.begin():
                page = await self._page_repository.get_by_key(session, key)
                if page is None:
                    page = await self._page_repository.create(session, key, content)
                else:
                    page.content = content
                    page.updated_at = datetime.utcnow()
                    session.add(page)
            return PageResult(key=key, content=content)

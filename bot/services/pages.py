from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.storage import PageRepository
from bot.utils import deserialize_entities

PAGE_KEY_FAQ = "faq"
PAGE_KEY_CONTACTS = "contacts"
PAGE_KEY_SCHEDULE = "schedule"
PAGE_KEY_PHOTO = "photo"

DEFAULT_PAGE_MESSAGE = "Эта страница пока не настроена."


@dataclass(frozen=True)
class PageResult:
    key: str
    content: str | None


@dataclass(frozen=True)
class PageRender:
    content_type: str
    text: str | None = None
    entities: list | None = None
    file_id: str | None = None
    caption: str | None = None
    caption_entities: list | None = None


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

    async def render_page(self, key: str) -> PageRender:
        async with self._session_maker() as session:
            page = await self._page_repository.get_by_key(session, key)
            if page is None:
                return PageRender(content_type="text", text=None)

            if page.content_type == "photo" and page.file_id:
                return PageRender(
                    content_type="photo",
                    file_id=page.file_id,
                    caption=page.caption or "",
                    caption_entities=deserialize_entities(page.caption_entities),
                )

            if page.content_type == "document" and page.file_id:
                return PageRender(
                    content_type="document",
                    file_id=page.file_id,
                    caption=page.caption or "",
                    caption_entities=deserialize_entities(page.caption_entities),
                )

            text = page.text if page.text is not None else page.content
            text = text.strip()
            if not text:
                return PageRender(content_type="text", text=None)
            return PageRender(
                content_type="text",
                text=text,
                entities=deserialize_entities(page.entities),
            )

    async def update_page(self, key: str, content: str) -> PageResult:
        async with self._session_maker() as session:
            async with session.begin():
                page = await self._page_repository.update_content_text(
                    session=session,
                    key=key,
                    text=content,
                    entities=None,
                )
                page.updated_at = datetime.utcnow()
            return PageResult(key=key, content=content)

    async def update_page_text(self, key: str, text: str, entities: list[dict] | None) -> None:
        async with self._session_maker() as session:
            async with session.begin():
                page = await self._page_repository.update_content_text(
                    session=session,
                    key=key,
                    text=text,
                    entities=entities,
                )
                page.updated_at = datetime.utcnow()

    async def update_page_photo(
        self,
        key: str,
        file_id: str,
        caption: str | None,
        caption_entities: list[dict] | None,
    ) -> None:
        async with self._session_maker() as session:
            async with session.begin():
                page = await self._page_repository.update_content_photo(
                    session=session,
                    key=key,
                    file_id=file_id,
                    caption=caption,
                    caption_entities=caption_entities,
                )
                page.updated_at = datetime.utcnow()

    async def update_page_document(
        self,
        key: str,
        file_id: str,
        caption: str | None,
        caption_entities: list[dict] | None,
    ) -> None:
        async with self._session_maker() as session:
            async with session.begin():
                page = await self._page_repository.update_content_document(
                    session=session,
                    key=key,
                    file_id=file_id,
                    caption=caption,
                    caption_entities=caption_entities,
                )
                page.updated_at = datetime.utcnow()

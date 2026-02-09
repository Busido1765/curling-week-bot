from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Page


class PageRepository:
    async def get_by_key(self, session: AsyncSession, key: str) -> Page | None:
        result = await session.execute(select(Page).where(Page.key == key))
        return result.scalar_one_or_none()

    async def create(self, session: AsyncSession, key: str, content: str) -> Page:
        page = Page(key=key, content=content)
        session.add(page)
        return page

    async def update_content_text(
        self,
        session: AsyncSession,
        key: str,
        text: str,
        entities: list[dict] | None,
    ) -> Page:
        page = await self.get_by_key(session, key)
        if page is None:
            page = Page(key=key, content=text, content_type="text", text=text, entities=entities)
        else:
            page.content_type = "text"
            page.content = text
            page.text = text
            page.entities = entities
            page.file_id = None
            page.caption = None
            page.caption_entities = None
        session.add(page)
        return page

    async def update_content_photo(
        self,
        session: AsyncSession,
        key: str,
        file_id: str,
        caption: str | None,
        caption_entities: list[dict] | None,
    ) -> Page:
        page = await self.get_by_key(session, key)
        safe_caption = caption or ""
        if page is None:
            page = Page(
                key=key,
                content=safe_caption,
                content_type="photo",
                file_id=file_id,
                caption=safe_caption,
                caption_entities=caption_entities,
            )
        else:
            page.content_type = "photo"
            page.content = safe_caption
            page.text = None
            page.entities = None
            page.file_id = file_id
            page.caption = safe_caption
            page.caption_entities = caption_entities
        session.add(page)
        return page

    async def update_content_document(
        self,
        session: AsyncSession,
        key: str,
        file_id: str,
        caption: str | None,
        caption_entities: list[dict] | None,
    ) -> Page:
        page = await self.get_by_key(session, key)
        safe_caption = caption or ""
        if page is None:
            page = Page(
                key=key,
                content=safe_caption,
                content_type="document",
                file_id=file_id,
                caption=safe_caption,
                caption_entities=caption_entities,
            )
        else:
            page.content_type = "document"
            page.content = safe_caption
            page.text = None
            page.entities = None
            page.file_id = file_id
            page.caption = safe_caption
            page.caption_entities = caption_entities
        session.add(page)
        return page

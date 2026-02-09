from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.models import RegistrationStatus
from bot.storage import UserRepository


class PageEditingService:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        user_repository: UserRepository,
    ) -> None:
        self._session_maker = session_maker
        self._user_repository = user_repository

    async def get_editing_key(self, tg_id: int) -> str | None:
        async with self._session_maker() as session:
            async with session.begin():
                user = await self._user_repository.get_by_tg_id(session, tg_id)
                if user is None:
                    return None
                return user.editing_page_key

    async def start_editing(self, tg_id: int, username: str | None, key: str) -> None:
        async with self._session_maker() as session:
            async with session.begin():
                user = await self._user_repository.get_by_tg_id(session, tg_id)
                if user is None:
                    user = await self._user_repository.create(
                        session, tg_id, username, RegistrationStatus.NONE
                    )
                await self._user_repository.set_editing_page_key(session, user, key)

    async def cancel_editing(self, tg_id: int) -> None:
        async with self._session_maker() as session:
            async with session.begin():
                user = await self._user_repository.get_by_tg_id(session, tg_id)
                if user is None:
                    return
                await self._user_repository.set_editing_page_key(session, user, None)

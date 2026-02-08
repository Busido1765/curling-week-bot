from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.models import RegistrationStatus
from bot.storage import UserRepository


class UserStatusService:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        user_repository: UserRepository,
    ) -> None:
        self._session_maker = session_maker
        self._user_repository = user_repository

    async def get_status(self, tg_id: int) -> RegistrationStatus | None:
        async with self._session_maker() as session:
            async with session.begin():
                user = await self._user_repository.get_by_tg_id(session, tg_id)
                if user is None:
                    return None
                return user.status

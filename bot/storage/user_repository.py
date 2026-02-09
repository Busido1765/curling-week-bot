from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import RegistrationStatus, User


class UserRepository:
    async def get_by_tg_id(self, session: AsyncSession, tg_id: int) -> User | None:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        session: AsyncSession,
        tg_id: int,
        username: str | None,
        status: RegistrationStatus,
    ) -> User:
        user = User(tg_id=tg_id, username=username, status=status)
        session.add(user)
        return user

    async def update_username(
        self, session: AsyncSession, user: User, username: str | None
    ) -> None:
        if user.username != username:
            user.username = username
            session.add(user)

    async def set_status(
        self, session: AsyncSession, user: User, status: RegistrationStatus
    ) -> None:
        if user.status != status:
            user.status = status
            session.add(user)

    async def set_editing_page_key(
        self, session: AsyncSession, user: User, key: str | None
    ) -> None:
        if user.editing_page_key != key:
            user.editing_page_key = key
            session.add(user)

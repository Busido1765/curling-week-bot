from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.models import RegistrationStatus, User
from bot.services.token_verifier import TokenVerifier
from bot.storage import UserRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StartResult:
    previous_status: RegistrationStatus
    current_status: RegistrationStatus
    token_provided: bool
    token_valid: bool | None


class RegistrationService:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        user_repository: UserRepository,
        token_verifier: TokenVerifier,
    ) -> None:
        self._session_maker = session_maker
        self._user_repository = user_repository
        self._token_verifier = token_verifier

    async def handle_start(
        self, tg_id: int, username: str | None, token: str | None
    ) -> StartResult:
        async with self._session_maker() as session:
            async with session.begin():
                user = await self._ensure_user(session, tg_id, username)
                previous_status = user.status

                if token is None:
                    await self._user_repository.set_status(
                        session, user, RegistrationStatus.NONE
                    )
                    current_status = user.status
                    logger.info(
                        "Start without token for tg_id=%s status=%s -> %s",
                        tg_id,
                        previous_status.value,
                        current_status.value,
                    )
                    return StartResult(
                        previous_status=previous_status,
                        current_status=current_status,
                        token_provided=False,
                        token_valid=None,
                    )

                token_valid = self._token_verifier.is_valid(token)
                logger.info(
                    "Token validation for tg_id=%s token_valid=%s",
                    tg_id,
                    token_valid,
                )

                if token_valid:
                    if user.status in {
                        RegistrationStatus.NONE,
                        RegistrationStatus.TOKEN_VERIFIED,
                    }:
                        await self._user_repository.set_status(
                            session, user, RegistrationStatus.TOKEN_VERIFIED
                        )
                current_status = user.status

                logger.info(
                    "Start with token for tg_id=%s status=%s -> %s",
                    tg_id,
                    previous_status.value,
                    current_status.value,
                )
                return StartResult(
                    previous_status=previous_status,
                    current_status=current_status,
                    token_provided=True,
                    token_valid=token_valid,
                )

    async def _ensure_user(
        self, session: AsyncSession, tg_id: int, username: str | None
    ) -> User:
        user = await self._user_repository.get_by_tg_id(session, tg_id)
        if user is None:
            user = await self._user_repository.create(
                session, tg_id, username, RegistrationStatus.NONE
            )
            return user

        await self._user_repository.update_username(session, user, username)
        return user

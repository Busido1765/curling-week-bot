from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.enums import ChatMemberStatus
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import RequiredChannel
from bot.models import RegistrationStatus
from bot.services.subscription_channels import get_required_channel_ids_for_check
from bot.storage import UserRepository

logger = logging.getLogger(__name__)

_RATE_LIMIT_SECONDS = 3.0
_last_check_by_user: dict[int, float] = {}


@dataclass(frozen=True)
class SubscriptionCheckResult:
    rate_limited: bool
    eligible: bool
    is_member: bool | None
    confirmed_now: bool
    error_message: str | None


class SubscriptionCheckerService:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        user_repository: UserRepository,
        required_channels: list[RequiredChannel],
        bot: Bot,
    ) -> None:
        self._session_maker = session_maker
        self._user_repository = user_repository
        self._required_channel_ids = get_required_channel_ids_for_check(
            required_channels
        )
        self._bot = bot

    async def check_subscription(
        self, tg_id: int, username: str | None
    ) -> SubscriptionCheckResult:
        if not self._required_channel_ids:
            logger.error("required_channels is empty after normalization")
            return SubscriptionCheckResult(
                rate_limited=False,
                eligible=False,
                is_member=None,
                confirmed_now=False,
                error_message="Регистрация временно недоступна. Попробуй позже.",
            )
        now = time.monotonic()
        last_check = _last_check_by_user.get(tg_id, 0.0)
        if now - last_check < _RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for tg_id=%s", tg_id)
            return SubscriptionCheckResult(
                rate_limited=True,
                eligible=False,
                is_member=None,
                confirmed_now=False,
                error_message=None,
            )
        _last_check_by_user[tg_id] = now

        async with self._session_maker() as session:
            async with session.begin():
                user = await self._user_repository.get_by_tg_id(session, tg_id)
                if user is None:
                    user = await self._user_repository.create(
                        session, tg_id, username, RegistrationStatus.NONE
                    )

                if user.status not in {
                    RegistrationStatus.TOKEN_VERIFIED,
                    RegistrationStatus.SUBSCRIPTION_VERIFIED,
                    RegistrationStatus.CONFIRMED,
                }:
                    logger.info(
                        "Subscription check denied for tg_id=%s status=%s",
                        tg_id,
                        user.status.value,
                    )
                    return SubscriptionCheckResult(
                        rate_limited=False,
                        eligible=False,
                        is_member=None,
                        confirmed_now=False,
                        error_message=None,
                    )

                is_member = True
                for channel_id in self._required_channel_ids:
                    try:
                        chat_member = await self._bot.get_chat_member(
                            channel_id, tg_id
                        )
                    except (TelegramForbiddenError, TelegramBadRequest) as exc:
                        logger.error(
                            "Failed to check subscription for tg_id=%s channel_id=%s: %s",
                            tg_id,
                            channel_id,
                            exc,
                        )
                        return SubscriptionCheckResult(
                            rate_limited=False,
                            eligible=True,
                            is_member=None,
                            confirmed_now=False,
                            error_message=(
                                "Не могу проверить подписку. Боту нужны права администратора в канале."
                            ),
                        )
                    status = chat_member.status
                    channel_member = status in {
                        ChatMemberStatus.MEMBER,
                        ChatMemberStatus.ADMINISTRATOR,
                        ChatMemberStatus.CREATOR,
                    }
                    logger.info(
                        "Subscription status for tg_id=%s channel_id=%s is_member=%s status=%s",
                        tg_id,
                        channel_id,
                        channel_member,
                        status,
                    )
                    if not channel_member:
                        is_member = False
                        break

                confirmed_now = False
                if is_member and user.status != RegistrationStatus.CONFIRMED:
                    await self._user_repository.set_status(
                        session, user, RegistrationStatus.CONFIRMED
                    )
                    confirmed_now = True

                return SubscriptionCheckResult(
                    rate_limited=False,
                    eligible=True,
                    is_member=is_member,
                    confirmed_now=confirmed_now,
                    error_message=None,
                )

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.services.registration import RegistrationService
from bot.services.subscription_checker import SubscriptionCheckerService
from bot.services.token_verifier import get_token_verifier
from bot.storage import UserRepository

router = Router()
logger = logging.getLogger(__name__)
CHECK_SUBSCRIPTION_CALLBACK = "check_subscription"


def _subscription_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data=CHECK_SUBSCRIPTION_CALLBACK,
                )
            ]
        ]
    )


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    token = None
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            token = parts[1]

    tg_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None
    logger.info("Received /start tg_id=%s token_provided=%s", tg_id, token is not None)

    service = RegistrationService(
        session_maker=message.bot.session_maker,
        user_repository=UserRepository(),
        token_verifier=get_token_verifier(),
    )
    result = await service.handle_start(tg_id=tg_id, username=username, token=token)

    if not result.token_provided:
        await message.answer(
            "Нужна регистрация на сайте. После регистрации открой ссылку, которая приведёт в бот"
        )
        return

    if result.token_valid:
        await message.answer(
            "Токен принят. Следующий шаг — проверка подписки на канал.",
            reply_markup=_subscription_keyboard(),
        )
        return

    await message.answer("Токен неверный/просрочен")


@router.callback_query(F.data == CHECK_SUBSCRIPTION_CALLBACK)
async def check_subscription_handler(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id if callback.from_user else 0
    username = callback.from_user.username if callback.from_user else None
    logger.info("Subscription check callback for tg_id=%s", tg_id)

    service = SubscriptionCheckerService(
        session_maker=callback.bot.session_maker,
        user_repository=UserRepository(),
        required_channel_id=callback.bot.settings.required_channel_id,
        bot=callback.bot,
    )
    result = await service.check_subscription(tg_id=tg_id, username=username)
    await callback.answer()

    if result.rate_limited:
        await callback.message.answer("Слишком часто, подожди 3 сек")
        return

    if not result.eligible:
        await callback.message.answer(
            "Нужна регистрация на сайте. После регистрации открой ссылку, которая приведёт в бот"
        )
        return

    if result.is_member:
        await callback.message.answer("Подписка подтверждена ✅")
        return

    await callback.message.answer("Подпишись на канал и нажми кнопку ещё раз")

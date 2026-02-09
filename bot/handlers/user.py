import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.keyboards import (
    CONTACTS_BUTTON,
    FAQ_BUTTON,
    PHOTO_BUTTON,
    SCHEDULE_BUTTON,
    confirmed_menu_keyboard,
)
from bot.keyboards.subscription import (
    CHECK_SUBSCRIPTION_CALLBACK,
    subscription_check_keyboard,
    subscription_links_keyboard,
)
from bot.models import RegistrationStatus
from bot.services.registration import RegistrationService
from bot.services.subscription_channels import build_subscription_channels_presentation
from bot.services.subscription_checker import SubscriptionCheckerService
from bot.services.token_verifier import get_token_verifier
from bot.services.user_status import UserStatusService
from bot.storage import UserRepository

router = Router()
logger = logging.getLogger(__name__)


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
        channels_presentation = build_subscription_channels_presentation(
            required_channel_ids=message.bot.settings.required_channel_ids,
            required_channel_links=message.bot.settings.required_channel_links,
        )
        reply_markup = None
        if channels_presentation.has_links:
            reply_markup = subscription_links_keyboard(channels_presentation.links)
        await message.answer(
            channels_presentation.message_text,
            reply_markup=reply_markup,
        )
        await message.answer(
            "После подписки вернись сюда и нажми кнопку:",
            reply_markup=subscription_check_keyboard(),
        )
        return

    await message.answer("Токен неверный/просрочен")


@router.callback_query(F.data == CHECK_SUBSCRIPTION_CALLBACK)
async def check_subscription_handler(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id if callback.from_user else 0
    username = callback.from_user.username if callback.from_user else None
    logger.info("Subscription check callback for tg_id=%s", tg_id)

    if not callback.bot.settings.required_channel_ids:
        logger.error("REQUIRED_CHANNEL_ID(S) is not configured")
        await callback.answer()
        await callback.message.answer(
            "Не настроен REQUIRED_CHANNEL_ID(S). Обратитесь к администратору."
        )
        return

    service = SubscriptionCheckerService(
        session_maker=callback.bot.session_maker,
        user_repository=UserRepository(),
        required_channel_ids=callback.bot.settings.required_channel_ids,
        bot=callback.bot,
    )
    result = await service.check_subscription(tg_id=tg_id, username=username)
    await callback.answer()

    if result.rate_limited:
        await callback.message.answer("Слишком часто. Подожди 3 сек.")
        return

    if result.error_message:
        await callback.message.answer(result.error_message)
        return

    if not result.eligible:
        await callback.message.answer(
            "Нужна регистрация на сайте. После регистрации открой ссылку, которая приведёт в бот"
        )
        return

    if result.is_member:
        reply_markup = None
        if result.confirmed_now:
            reply_markup = confirmed_menu_keyboard()
        await callback.message.answer("Подписка подтверждена ✅", reply_markup=reply_markup)
        return

    await callback.message.answer(
        "Ты не подписан на канал. Подпишись и нажми кнопку ещё раз."
    )


@router.message(
    F.text
    & ~F.text.startswith("/")
    & ~F.text.in_({SCHEDULE_BUTTON, FAQ_BUTTON, CONTACTS_BUTTON, PHOTO_BUTTON})
)
async def confirmed_user_fallback(message: Message) -> None:
    if message.from_user is None:
        return
    service = UserStatusService(
        session_maker=message.bot.session_maker,
        user_repository=UserRepository(),
    )
    status = await service.get_status(message.from_user.id)
    if status != RegistrationStatus.CONFIRMED:
        return
    await message.answer("Выберите пункт меню", reply_markup=confirmed_menu_keyboard())

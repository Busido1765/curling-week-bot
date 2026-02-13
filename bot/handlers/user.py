import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.keyboards import (
    BACK_BUTTON,
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
from bot.services.subscription_channels import (
    build_subscription_channels_presentation,
    get_required_channel_ids_for_check,
)
from bot.services.subscription_checker import SubscriptionCheckerService
from bot.services.token_verifier import get_token_verifier
from bot.services.user_status import UserStatusService
from bot.services.page_editing import PageEditingService
from bot.storage import UserRepository
from bot.handlers.admin import PageEditingStates, PostCreationStates

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    logger.info("DEBUG: start_handler triggered")
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
            "Чтобы участвовать в «Неделе кёрлинга в Москве», нужно зарегистрироваться на официальном сайте проекта.\n\n"
            "После регистрации ты получишь персональную ссылку для входа в бот. Мы также продублируем её на почту — она пригодится, если захочешь вернуться позже.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="Перейти к регистрации →",
                            url="https://curlingweek.sport.moscow/",
                        )
                    ]
                ]
            ),
        )
        return

    if result.token_valid:
        required_channel_ids = get_required_channel_ids_for_check(
            message.bot.settings.required_channels
        )
        if not required_channel_ids:
            logger.error("required_channels is empty after normalization")
            await message.answer(
                "Проверка временно недоступна. Попробуй позже."
            )
            return
        channels_presentation = build_subscription_channels_presentation(
            required_channels=message.bot.settings.required_channels,
        )
        reply_markup = None
        if channels_presentation.has_links:
            reply_markup = subscription_links_keyboard(channels_presentation.links)
        await message.answer(
            channels_presentation.message_text,
            reply_markup=reply_markup,
        )
        await message.answer(
            "После подписки вернись в бота и подтверди подписку:",
            reply_markup=subscription_check_keyboard(),
        )
        return

    await message.answer("Ошибка доступа")


@router.callback_query(F.data == CHECK_SUBSCRIPTION_CALLBACK)
async def check_subscription_handler(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id if callback.from_user else 0
    username = callback.from_user.username if callback.from_user else None
    logger.info("Subscription check callback for tg_id=%s", tg_id)

    service = SubscriptionCheckerService(
        session_maker=callback.bot.session_maker,
        user_repository=UserRepository(),
        required_channels=callback.bot.settings.required_channels,
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
        await callback.message.answer(
            """🥌 Ты в деле — добро пожаловать в бот «Неделя кёрлинга» в Москве!
Регистрация есть ✅
Подписка на канал Федерации тоже ✅

➡️ Дальше всё просто: этот бот — твой «штаб» на время проекта.

Зачем он нужен?
Чтобы не искать информацию по чатам и постам — мы будем присылать сюда:
— быстрые апдейты (если что-то поменялось по времени/площадке)
— фотки и лучшие моменты дня 📸
— короткие подсказки для новичков (чтобы на льду чувствовать себя уверенно)

Оставайся с нами — будет движ и кёрлинг ❤️""",
            reply_markup=reply_markup
        )
        return

    await callback.message.answer(
        "Ты не подписан на нужный канал. Подпишись и нажми кнопку ещё раз."
    )




@router.message(F.text == BACK_BUTTON)
async def back_button_handler(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state in {
        PostCreationStates.waiting_for_content.state,
        PageEditingStates.waiting_for_content.state,
    }:
        await message.answer("Ты в режиме редактирования. Нажми ❌ Отмена.")
        return

    await message.answer("Выбери раздел 👇", reply_markup=confirmed_menu_keyboard())

@router.message(
    ~StateFilter(PostCreationStates.waiting_for_content),
    ~StateFilter(PageEditingStates.waiting_for_content),
    F.text
    & ~F.text.startswith("/")
    & ~F.text.in_({SCHEDULE_BUTTON, FAQ_BUTTON, CONTACTS_BUTTON, PHOTO_BUTTON, BACK_BUTTON})
)
async def confirmed_user_fallback(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    current_state = await state.get_state()
    admin_id = message.from_user.id if message.from_user else None
    logger.info(
        "GENERIC_TEXT_HANDLER hit state=%s admin_id=%s text_prefix=%r",
        current_state,
        admin_id,
        (message.text or "")[:30],
    )
    editing_service = PageEditingService(
        session_maker=message.bot.session_maker,
        user_repository=UserRepository(),
    )
    editing_key = await editing_service.get_editing_key(message.from_user.id)
    if editing_key is not None:
        return
    service = UserStatusService(
        session_maker=message.bot.session_maker,
        user_repository=UserRepository(),
    )
    status = await service.get_status(message.from_user.id)
    if status != RegistrationStatus.CONFIRMED:
        return
    await message.answer("Выберите пункт меню", reply_markup=confirmed_menu_keyboard())

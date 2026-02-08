from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup

from bot.keyboards import (
    CONTACTS_BUTTON,
    FAQ_BUTTON,
    PHOTO_BUTTON,
    SCHEDULE_BUTTON,
    confirmed_menu_keyboard,
)
from bot.models import RegistrationStatus
from bot.services.pages import (
    DEFAULT_PAGE_MESSAGE,
    PAGE_KEY_CONTACTS,
    PAGE_KEY_FAQ,
    PAGE_KEY_PHOTO,
    PAGE_KEY_SCHEDULE,
    PageService,
)
from bot.services.user_status import UserStatusService
from bot.storage import PageRepository
from bot.storage import UserRepository

router = Router()


async def _get_confirmed_menu(message: Message) -> ReplyKeyboardMarkup | None:
    if message.from_user is None:
        return None
    service = UserStatusService(
        session_maker=message.bot.session_maker,
        user_repository=UserRepository(),
    )
    status = await service.get_status(message.from_user.id)
    if status == RegistrationStatus.CONFIRMED:
        return confirmed_menu_keyboard()
    return None


async def _send_page(message: Message, key: str) -> None:
    service = PageService(
        session_maker=message.bot.session_maker,
        page_repository=PageRepository(),
    )
    result = await service.get_page(key)
    content = result.content or DEFAULT_PAGE_MESSAGE
    reply_markup = await _get_confirmed_menu(message)
    await message.answer(content, reply_markup=reply_markup)


@router.message(Command("faq"))
async def faq_handler(message: Message) -> None:
    await _send_page(message, PAGE_KEY_FAQ)


@router.message(Command("contacts"))
async def contacts_handler(message: Message) -> None:
    await _send_page(message, PAGE_KEY_CONTACTS)


@router.message(Command("schedule"))
async def schedule_handler(message: Message) -> None:
    await _send_page(message, PAGE_KEY_SCHEDULE)


@router.message(Command("photo"))
async def photo_handler(message: Message) -> None:
    await _send_page(message, PAGE_KEY_PHOTO)


@router.message(F.text == FAQ_BUTTON)
async def faq_button_handler(message: Message) -> None:
    await _send_page(message, PAGE_KEY_FAQ)


@router.message(F.text == CONTACTS_BUTTON)
async def contacts_button_handler(message: Message) -> None:
    await _send_page(message, PAGE_KEY_CONTACTS)


@router.message(F.text == SCHEDULE_BUTTON)
async def schedule_button_handler(message: Message) -> None:
    await _send_page(message, PAGE_KEY_SCHEDULE)


@router.message(F.text == PHOTO_BUTTON)
async def photo_button_handler(message: Message) -> None:
    await _send_page(message, PAGE_KEY_PHOTO)

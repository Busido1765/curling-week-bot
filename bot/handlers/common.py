from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services.pages import (
    DEFAULT_PAGE_MESSAGE,
    PAGE_KEY_CONTACTS,
    PAGE_KEY_FAQ,
    PAGE_KEY_PHOTO,
    PAGE_KEY_SCHEDULE,
    PageService,
)
from bot.storage import PageRepository

router = Router()


async def _send_page(message: Message, key: str) -> None:
    service = PageService(
        session_maker=message.bot.session_maker,
        page_repository=PageRepository(),
    )
    result = await service.get_page(key)
    content = result.content or DEFAULT_PAGE_MESSAGE
    await message.answer(content)


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

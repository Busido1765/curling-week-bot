from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards.page_edit import EDIT_PAGE_CALLBACK_PREFIX, page_edit_keyboard
from bot.services.page_editing import PageEditingService
from bot.services.pages import (
    DEFAULT_PAGE_MESSAGE,
    PAGE_KEY_CONTACTS,
    PAGE_KEY_FAQ,
    PAGE_KEY_PHOTO,
    PAGE_KEY_SCHEDULE,
    PageService,
)
from bot.storage import PageRepository, UserRepository


router = Router()
PAGE_KEYS = {PAGE_KEY_FAQ, PAGE_KEY_CONTACTS, PAGE_KEY_SCHEDULE, PAGE_KEY_PHOTO}


@router.message(Command("admin"))
async def admin_menu(message: Message) -> None:
    settings = message.bot.settings
    if message.from_user is None or message.from_user.id not in settings.admin_ids:
        await message.answer("Access denied")
        return
    await message.answer("Admin menu is under construction")


def _is_admin(message: Message) -> bool:
    if message.from_user is None:
        return False
    return message.from_user.id in message.bot.settings.admin_ids


def _is_admin_callback(callback: CallbackQuery) -> bool:
    if callback.from_user is None:
        return False
    return callback.from_user.id in callback.bot.settings.admin_ids


async def _send_page_with_edit_button(message: Message, key: str) -> None:
    service = PageService(
        session_maker=message.bot.session_maker,
        page_repository=PageRepository(),
    )
    result = await service.get_page(key)
    content = result.content or DEFAULT_PAGE_MESSAGE
    await message.answer(content, reply_markup=page_edit_keyboard(key))


@router.callback_query(F.data.startswith(EDIT_PAGE_CALLBACK_PREFIX))
async def edit_page_callback(callback: CallbackQuery) -> None:
    if not _is_admin_callback(callback):
        await callback.answer("Недостаточно прав")
        return
    data = callback.data or ""
    page_key = data[len(EDIT_PAGE_CALLBACK_PREFIX) :]
    if page_key not in PAGE_KEYS:
        await callback.answer("Недоступная страница")
        return
    service = PageEditingService(
        session_maker=callback.bot.session_maker,
        user_repository=UserRepository(),
    )
    await service.start_editing(
        tg_id=callback.from_user.id,
        username=callback.from_user.username,
        key=page_key,
    )
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            f"Пришли новый текст для {page_key}. Для отмены: /cancel"
        )


@router.message(Command("cancel"))
async def cancel_editing(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("Недостаточно прав")
        return
    service = PageEditingService(
        session_maker=message.bot.session_maker,
        user_repository=UserRepository(),
    )
    await service.cancel_editing(message.from_user.id)
    await message.answer("Отменено")


@router.message(F.text & ~F.text.startswith("/"))
async def handle_page_editing(message: Message) -> None:
    if not _is_admin(message):
        return
    service = PageEditingService(
        session_maker=message.bot.session_maker,
        user_repository=UserRepository(),
    )
    editing_key = await service.get_editing_key(message.from_user.id)
    if editing_key is None:
        return
    page_service = PageService(
        session_maker=message.bot.session_maker,
        page_repository=PageRepository(),
    )
    await page_service.update_page(editing_key, message.text or "")
    await service.cancel_editing(message.from_user.id)
    await message.answer("Сохранено ✅")
    await _send_page_with_edit_button(message, editing_key)

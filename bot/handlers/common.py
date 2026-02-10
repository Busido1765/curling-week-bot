import logging

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
from bot.keyboards.page_edit import page_edit_keyboard
from bot.models import RegistrationStatus
from bot.services.page_editing import PageEditingService
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
from bot.utils.admin import is_admin_event

router = Router()
logger = logging.getLogger(__name__)


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


def _is_admin(message: Message) -> bool:
    return is_admin_event(message)


async def _send_page(message: Message, key: str) -> None:
    user_id = message.from_user.id if message.from_user else None
    is_admin = _is_admin(message)
    logger.info("PAGE_VIEW_HANDLER hit page=%s user_id=%s is_admin=%s", key, user_id, is_admin)

    service = PageService(
        session_maker=message.bot.session_maker,
        page_repository=PageRepository(),
    )
    render = await service.render_page(key)
    reply_markup = None
    if is_admin:
        reply_markup = page_edit_keyboard(key)
    else:
        reply_markup = await _get_confirmed_menu(message)
    if render.main_content_type == "photo" and render.main_photo_file_id:
        logger.info("PAGE_VIEW_HANDLER content_length=%s", len(render.main_photo_caption or ""))
        await message.answer_photo(
            render.main_photo_file_id,
            caption=render.main_photo_caption,
            caption_entities=render.main_photo_caption_entities,
            reply_markup=reply_markup,
        )
        if render.extra_document_file_id:
            await message.answer_document(
                render.extra_document_file_id,
                caption=render.extra_document_caption,
                caption_entities=render.extra_document_caption_entities,
            )
        return

    if render.main_text:
        logger.info("PAGE_VIEW_HANDLER content_length=%s", len(render.main_text))
        await message.answer(render.main_text, reply_markup=reply_markup, entities=render.main_entities)
        if render.extra_document_file_id:
            await message.answer_document(
                render.extra_document_file_id,
                caption=render.extra_document_caption,
                caption_entities=render.extra_document_caption_entities,
            )
        return

    if render.extra_document_file_id:
        logger.info("PAGE_VIEW_HANDLER content_length=%s", len(render.extra_document_caption or ""))
        await message.answer_document(
            render.extra_document_file_id,
            caption=render.extra_document_caption,
            caption_entities=render.extra_document_caption_entities,
            reply_markup=reply_markup,
        )
        return

    logger.info("PAGE_VIEW_HANDLER content_length=%s", len(DEFAULT_PAGE_MESSAGE))
    await message.answer(DEFAULT_PAGE_MESSAGE, reply_markup=reply_markup)


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

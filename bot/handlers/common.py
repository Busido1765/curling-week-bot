import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup

from bot.keyboards import (
    CONTACTS_BUTTON,
    FAQ_BUTTON,
    PHOTO_BUTTON,
    SCHEDULE_BUTTON,
    back_keyboard,
)
from bot.keyboards.page_edit import page_edit_keyboard
from bot.services.pages import (
    DEFAULT_PAGE_MESSAGE,
    PAGE_KEY_CONTACTS,
    PAGE_KEY_FAQ,
    PAGE_KEY_PHOTO,
    PAGE_KEY_SCHEDULE,
    PageService,
)
from bot.storage import PageRepository
from bot.utils.admin import is_admin_event

router = Router()
logger = logging.getLogger(__name__)


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

    admin_markup: ReplyKeyboardMarkup | None = page_edit_keyboard(key) if is_admin else None
    user_markup: ReplyKeyboardMarkup | None = None if is_admin else back_keyboard()

    if render.main_content_type == "photo" and render.main_photo_file_id:
        logger.info("PAGE_VIEW_HANDLER content_length=%s", len(render.main_photo_caption or ""))
        await message.answer_photo(
            render.main_photo_file_id,
            caption=render.main_photo_caption,
            caption_entities=render.main_photo_caption_entities,
            reply_markup=admin_markup,
        )
        if render.extra_document_file_id:
            await message.answer_document(
                render.extra_document_file_id,
                caption=render.extra_document_caption,
                caption_entities=render.extra_document_caption_entities,
                reply_markup=user_markup,
            )
            return
        if user_markup:
            await message.answer("Выбери раздел 👇", reply_markup=user_markup)
        return

    if render.main_text:
        logger.info("PAGE_VIEW_HANDLER content_length=%s", len(render.main_text))
        if render.extra_document_file_id:
            await message.answer(render.main_text, reply_markup=admin_markup, entities=render.main_entities)
            await message.answer_document(
                render.extra_document_file_id,
                caption=render.extra_document_caption,
                caption_entities=render.extra_document_caption_entities,
                reply_markup=user_markup,
            )
            return
        await message.answer(
            render.main_text,
            reply_markup=admin_markup or user_markup,
            entities=render.main_entities,
        )
        return

    if render.extra_document_file_id:
        logger.info("PAGE_VIEW_HANDLER content_length=%s", len(render.extra_document_caption or ""))
        await message.answer_document(
            render.extra_document_file_id,
            caption=render.extra_document_caption,
            caption_entities=render.extra_document_caption_entities,
            reply_markup=admin_markup or user_markup,
        )
        return

    logger.info("PAGE_VIEW_HANDLER content_length=%s", len(DEFAULT_PAGE_MESSAGE))
    await message.answer(DEFAULT_PAGE_MESSAGE, reply_markup=admin_markup or user_markup)


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

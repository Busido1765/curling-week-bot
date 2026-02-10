import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.filters import Command

from bot.keyboards.page_edit import EDIT_PAGE_CALLBACK_PREFIX, page_edit_keyboard
from bot.keyboards.post_confirm import (
    POST_CANCEL_CALLBACK,
    POST_CLEAR_CALLBACK,
    POST_PREVIEW_CALLBACK,
    POST_SEND_CALLBACK,
    post_cancel_keyboard,
    post_confirm_keyboard,
)
from bot.services.page_editing import PageEditingService
from bot.services.pages import (
    DEFAULT_PAGE_MESSAGE,
    PAGE_KEY_CONTACTS,
    PAGE_KEY_FAQ,
    PAGE_KEY_PHOTO,
    PAGE_KEY_SCHEDULE,
    PageService,
)
from bot.services.post_service import PostService, UnsupportedPostContentError
from bot.storage import PageRepository, PostRepository, UserRepository
from bot.utils import serialize_entities


router = Router()
PAGE_KEYS = {PAGE_KEY_FAQ, PAGE_KEY_CONTACTS, PAGE_KEY_SCHEDULE, PAGE_KEY_PHOTO}
logger = logging.getLogger(__name__)


class PostCreationStates(StatesGroup):
    waiting_for_content = State()


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
    render = await service.render_page(key)
    reply_markup = page_edit_keyboard(key)
    if render.content_type == "photo" and render.file_id:
        await message.answer_photo(
            render.file_id,
            caption=render.caption,
            caption_entities=render.caption_entities,
            reply_markup=reply_markup,
        )
        return
    if render.content_type == "document" and render.file_id:
        await message.answer_document(
            render.file_id,
            caption=render.caption,
            caption_entities=render.caption_entities,
            reply_markup=reply_markup,
        )
        return
    content = render.text or DEFAULT_PAGE_MESSAGE
    await message.answer(content, reply_markup=reply_markup, entities=render.entities)


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
            f"Пришли новый текст, фото или документ для {page_key}. Для отмены: /cancel"
        )


@router.message(Command("post"))
async def start_post_creation(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        await message.answer("Недостаточно прав")
        return
    service = PostService(
        session_maker=message.bot.session_maker,
        post_repository=PostRepository(),
    )
    await service.ensure_draft(message.from_user.id)
    await state.set_state(PostCreationStates.waiting_for_content)
    await message.answer(
        "Создаём анонс для участников 👇\n"
        "Пришли сообщением:\n"
        "• текст (можно с форматированием Telegram)\n"
        "и/или\n"
        "• фото/видео/гиф (можно с подписью)\n"
        "и/или\n"
        "• файл (документ) — он будет отправлен участникам ОТДЕЛЬНЫМ сообщением после основного поста.\n\n"
        "Можно отправлять в любом порядке — я соберу черновик и сразу покажу превью.\n"
        "Отменить создание — нажми «❌ Отмена».",
        reply_markup=post_cancel_keyboard(),
    )


async def _handle_post_content(message: Message) -> None:
    if not _is_admin(message) or message.from_user is None:
        return
    content_type = (
        "text"
        if message.text
        else "photo"
        if message.photo
        else "video"
        if message.video
        else "animation"
        if message.animation
        else "document"
        if message.document
        else "unsupported"
    )
    logger.info("Post content received type=%s admin_id=%s", content_type, message.from_user.id)

    service = PostService(
        session_maker=message.bot.session_maker,
        post_repository=PostRepository(),
    )
    try:
        result = await service.apply_message_to_draft(message.from_user.id, message)
    except UnsupportedPostContentError as exc:
        if str(exc) == "album":
            await message.answer(
                "Альбомы не поддерживаются. Пришли одно фото/видео/гиф одним сообщением.",
                reply_markup=post_cancel_keyboard(),
            )
            return
        await message.answer(
            "Этот тип сообщения не подходит для анонса. Пришли текст, фото/видео/гиф или файл (документ).",
            reply_markup=post_cancel_keyboard(),
        )
        return

    await service.send_preview(message.bot, message.chat.id, result.post)
    if result.notice:
        await message.answer(result.notice)
    await message.answer("Черновик обновлён.", reply_markup=post_confirm_keyboard())


@router.message(
    StateFilter(PostCreationStates.waiting_for_content),
    F.text,
)
async def post_text_handler(message: Message) -> None:
    admin_id = message.from_user.id if message.from_user else None
    text_prefix = (message.text or "")[:30]
    logger.info("post_text_handler hit admin_id=%s text_prefix=%r", admin_id, text_prefix)
    if (message.text or "").startswith("/"):
        await message.answer(
            "Ты в режиме создания поста. Нажми ❌ Отмена или пришли контент.",
            reply_markup=post_cancel_keyboard(),
        )
        return
    await _handle_post_content(message)


@router.message(
    StateFilter(PostCreationStates.waiting_for_content),
    F.photo | F.video | F.animation | F.document,
)
async def handle_post_media_content(message: Message) -> None:
    await _handle_post_content(message)


@router.message(PostCreationStates.waiting_for_content)
async def handle_post_unsupported(message: Message) -> None:
    if not _is_admin(message):
        return
    if message.media_group_id:
        await message.answer(
            "Альбомы не поддерживаются. Пришли одно фото/видео/гиф одним сообщением.",
            reply_markup=post_cancel_keyboard(),
        )
        return
    await message.answer(
        "Этот тип сообщения не подходит для анонса. Пришли текст, фото/видео/гиф или файл (документ).",
        reply_markup=post_cancel_keyboard(),
    )


@router.message(Command("cancel"))
async def cancel_editing(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        await message.answer("Недостаточно прав")
        return
    await state.clear()
    service = PageEditingService(
        session_maker=message.bot.session_maker,
        user_repository=UserRepository(),
    )
    await service.cancel_editing(message.from_user.id)
    await message.answer("Отменено")


@router.callback_query(F.data == POST_PREVIEW_CALLBACK)
async def preview_post_callback(callback: CallbackQuery) -> None:
    if not _is_admin_callback(callback) or callback.from_user is None:
        await callback.answer("Недостаточно прав")
        return
    post_service = PostService(
        session_maker=callback.bot.session_maker,
        post_repository=PostRepository(),
    )
    draft = await post_service.get_active_draft(callback.from_user.id)
    if not draft or post_service.is_draft_empty(draft):
        await callback.answer("Черновик пуст", show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await post_service.send_preview(callback.bot, callback.message.chat.id, draft)
        await callback.message.answer("Это превью.", reply_markup=post_confirm_keyboard())


@router.callback_query(F.data == POST_CLEAR_CALLBACK)
async def clear_post_callback(callback: CallbackQuery) -> None:
    if not _is_admin_callback(callback) or callback.from_user is None:
        await callback.answer("Недостаточно прав")
        return
    post_service = PostService(
        session_maker=callback.bot.session_maker,
        post_repository=PostRepository(),
    )
    await post_service.cancel_draft(callback.from_user.id)
    await callback.answer()
    if callback.message:
        await callback.message.answer("Создание анонса отменено.")


@router.callback_query(F.data == POST_CANCEL_CALLBACK)
async def cancel_post_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin_callback(callback) or callback.from_user is None:
        await callback.answer("Недостаточно прав")
        return
    post_service = PostService(
        session_maker=callback.bot.session_maker,
        post_repository=PostRepository(),
    )
    await post_service.cancel_draft(callback.from_user.id)
    await state.clear()
    await callback.answer()
    if callback.message:
        await callback.message.answer("Создание анонса отменено.")


@router.callback_query(F.data == POST_SEND_CALLBACK)
async def send_post_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin_callback(callback) or callback.from_user is None:
        await callback.answer("Недостаточно прав")
        return

    settings = callback.bot.settings
    post_service = PostService(
        session_maker=callback.bot.session_maker,
        post_repository=PostRepository(),
    )
    draft = await post_service.get_active_draft(callback.from_user.id)
    if not draft or post_service.is_draft_empty(draft):
        await callback.answer()
        if callback.message:
            await callback.message.answer(
                "Нечего отправлять: черновик пустой. Создание анонса отменено."
            )
        await post_service.cancel_draft(callback.from_user.id)
        await state.clear()
        return

    await callback.answer()
    if callback.message:
        await callback.message.answer("Начинаю рассылку…")

    success_count, fail_count = await post_service.broadcast_draft(
        callback.bot,
        draft,
        user_repository=UserRepository(),
        send_delay_seconds=settings.broadcast_delay_seconds,
        batch_log_every=settings.broadcast_batch_log_every,
    )
    await state.clear()
    if callback.message:
        await callback.message.answer("✅ Отправлено всем участникам.")
        await callback.message.answer(
            f"Готово. Успешно: {success_count}, Ошибок: {fail_count}"
        )


@router.message((F.text & ~F.text.startswith("/")) | F.photo | F.document)
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
    if message.photo:
        file_id = message.photo[-1].file_id
        await page_service.update_page_photo(
            editing_key,
            file_id=file_id,
            caption=message.caption,
            caption_entities=serialize_entities(message.caption_entities),
        )
    elif message.document:
        await page_service.update_page_document(
            editing_key,
            file_id=message.document.file_id,
            caption=message.caption,
            caption_entities=serialize_entities(message.caption_entities),
        )
    elif message.text:
        await page_service.update_page_text(
            editing_key,
            text=message.text,
            entities=serialize_entities(message.entities),
        )
    else:
        await message.answer("Пока поддерживаются: текст, фото, документ.")
        return
    await service.cancel_editing(message.from_user.id)
    await message.answer("Сохранено ✅")
    await _send_page_with_edit_button(message, editing_key)


@router.message(~Command())
async def handle_page_editing_unsupported(message: Message) -> None:
    if not _is_admin(message):
        return
    service = PageEditingService(
        session_maker=message.bot.session_maker,
        user_repository=UserRepository(),
    )
    editing_key = await service.get_editing_key(message.from_user.id)
    if editing_key is None:
        return
    if message.text or message.photo or message.document:
        return
    await message.answer("Пока поддерживаются: текст, фото, документ.")

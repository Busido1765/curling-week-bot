import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.filters import Command

from bot.keyboards.page_edit import EDIT_PAGE_CALLBACK_PREFIX, page_edit_keyboard
from bot.keyboards.post_confirm import (
    POST_CANCEL_CALLBACK_PREFIX,
    POST_SEND_CALLBACK_PREFIX,
    post_confirm_keyboard,
)
from bot.services.broadcast import BroadcastService
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
    await state.set_state(PostCreationStates.waiting_for_content)
    await message.answer(
        "Пришли текст/фото/файл для анонса. Можно с форматированием как в Telegram."
    )


async def _handle_post_content(message: Message, state: FSMContext, content_type: str) -> None:
    if not _is_admin(message):
        return
    logger.info(
        "Post content received type=%s admin_id=%s",
        content_type,
        message.from_user.id if message.from_user else None,
    )
    service = PostService(
        session_maker=message.bot.session_maker,
        post_repository=PostRepository(),
    )
    try:
        post = await service.create_draft_from_message(message.from_user.id, message)
    except UnsupportedPostContentError:
        await message.answer("Пока поддерживаются: текст, фото, документ.")
        return

    await state.clear()
    await service.render_post_to_chat(message.bot, message.chat.id, post)
    await message.answer(
        "Отправить всем?",
        reply_markup=post_confirm_keyboard(post.id),
    )


@router.message(PostCreationStates.waiting_for_content, F.text, ~Command())
async def handle_post_text(message: Message, state: FSMContext) -> None:
    await _handle_post_content(message, state, "text")


@router.message(PostCreationStates.waiting_for_content, F.photo)
async def handle_post_photo(message: Message, state: FSMContext) -> None:
    await _handle_post_content(message, state, "photo")


@router.message(PostCreationStates.waiting_for_content, F.document)
async def handle_post_document(message: Message, state: FSMContext) -> None:
    await _handle_post_content(message, state, "document")


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


@router.callback_query(F.data.startswith(POST_CANCEL_CALLBACK_PREFIX))
async def cancel_post_callback(callback: CallbackQuery) -> None:
    if not _is_admin_callback(callback):
        await callback.answer("Недостаточно прав")
        return
    data = callback.data or ""
    post_id_raw = data[len(POST_CANCEL_CALLBACK_PREFIX) :]
    if not post_id_raw.isdigit():
        await callback.answer("Некорректный пост")
        return
    post_id = int(post_id_raw)
    post_repository = PostRepository()
    async with callback.bot.session_maker() as session:
        async with session.begin():
            post = await post_repository.get(session, post_id)
            if post is None:
                await callback.answer("Пост не найден")
                return
            if post.status != "draft":
                await callback.answer("Уже отправлено/отменено")
                return
            await post_repository.mark_canceled(session, post_id)
    await callback.answer()
    if callback.message:
        await callback.message.answer("Отменено")


@router.callback_query(F.data.startswith(POST_SEND_CALLBACK_PREFIX))
async def send_post_callback(callback: CallbackQuery) -> None:
    if not _is_admin_callback(callback):
        await callback.answer("Недостаточно прав")
        return
    data = callback.data or ""
    post_id_raw = data[len(POST_SEND_CALLBACK_PREFIX) :]
    if not post_id_raw.isdigit():
        await callback.answer("Некорректный пост")
        return
    post_id = int(post_id_raw)

    async with callback.bot.session_maker() as session:
        post_repository = PostRepository()
        post = await post_repository.get(session, post_id)
        if post is None:
            await callback.answer("Пост не найден")
            return
        if post.status != "draft":
            await callback.answer("Уже отправлено/отменено")
            return

    await callback.answer()
    if callback.message:
        await callback.message.answer("Начинаю рассылку…")

    settings = callback.bot.settings
    post_service = PostService(
        session_maker=callback.bot.session_maker,
        post_repository=PostRepository(),
    )
    broadcast_service = BroadcastService(
        session_maker=callback.bot.session_maker,
        post_repository=PostRepository(),
        user_repository=UserRepository(),
        post_service=post_service,
        send_delay_seconds=settings.broadcast_delay_seconds,
        batch_log_every=settings.broadcast_batch_log_every,
    )
    try:
        success_count, fail_count = await broadcast_service.broadcast_post(
            callback.bot, post_id
        )
    except ValueError:
        if callback.message:
            await callback.message.answer("Уже отправлено/отменено")
        return
    if callback.message:
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

import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.filters import Command

from bot.keyboards.page_edit import (
    EDIT_PAGE_CALLBACK_PREFIX,
    PAGE_DRAFT_CANCEL_CALLBACK,
    PAGE_DRAFT_SAVE_CALLBACK,
    page_draft_cancel_keyboard,
    page_draft_confirm_keyboard,
    page_edit_keyboard,
)
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
from bot.utils import serialize_entities, should_notify_album, should_notify_document_update
from bot.utils.admin import is_admin_event


router = Router()
PAGE_KEYS = {PAGE_KEY_FAQ, PAGE_KEY_CONTACTS, PAGE_KEY_SCHEDULE, PAGE_KEY_PHOTO}
logger = logging.getLogger(__name__)

def _should_send_album_warning(message: Message) -> bool:
    if not message.media_group_id:
        return False
    return should_notify_album(message.chat.id, message.media_group_id)


def _is_document_notice_allowed(message: Message) -> bool:
    if message.from_user is None:
        return False
    return should_notify_document_update(chat_id=message.chat.id, user_id=message.from_user.id)


class PostCreationStates(StatesGroup):
    waiting_for_content = State()


class PageEditingStates(StatesGroup):
    waiting_for_content = State()


@router.message(Command("admin"))
async def admin_menu(message: Message) -> None:
    settings = message.bot.settings
    if message.from_user is None or message.from_user.id not in settings.admin_ids:
        await message.answer("Access denied")
        return
    await message.answer("Admin menu is under construction")


def _is_admin(message: Message | CallbackQuery) -> bool:
    return is_admin_event(message)


async def _send_page_with_edit_button(message: Message, key: str) -> None:
    service = PageService(
        session_maker=message.bot.session_maker,
        page_repository=PageRepository(),
    )
    render = await service.render_page(key)
    reply_markup = page_edit_keyboard(key)
    if render.main_content_type == "photo" and render.main_photo_file_id:
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
        await message.answer(render.main_text, reply_markup=reply_markup, entities=render.main_entities)
        if render.extra_document_file_id:
            await message.answer_document(
                render.extra_document_file_id,
                caption=render.extra_document_caption,
                caption_entities=render.extra_document_caption_entities,
            )
        return

    if render.extra_document_file_id:
        await message.answer_document(
            render.extra_document_file_id,
            caption=render.extra_document_caption,
            caption_entities=render.extra_document_caption_entities,
            reply_markup=reply_markup,
        )
        return

    await message.answer(DEFAULT_PAGE_MESSAGE, reply_markup=reply_markup)


async def _start_page_editing(
    message: Message,
    state: FSMContext,
    page_key: str,
    user_id: int | None = None,
    username: str | None = None,
) -> None:
    if page_key not in PAGE_KEYS:
        await message.answer("Недоступная страница")
        return

    if user_id is None:
        if not _is_admin(message) or message.from_user is None:
            await message.answer("Недостаточно прав")
            return
        actor_user_id = message.from_user.id
        actor_username = message.from_user.username
    else:
        if user_id not in message.bot.settings.admin_ids:
            await message.answer("Недостаточно прав")
            return
        actor_user_id = user_id
        actor_username = username

    service = PageEditingService(
        session_maker=message.bot.session_maker,
        user_repository=UserRepository(),
    )
    await service.start_editing(
        tg_id=actor_user_id,
        username=actor_username,
        key=page_key,
    )
    page_service = PageService(
        session_maker=message.bot.session_maker,
        page_repository=PageRepository(),
    )
    render = await page_service.render_page(page_key)
    draft = {"key": page_key}
    if render.main_content_type == "photo" and render.main_photo_file_id:
        draft.update(
            {
                "main_content_type": "photo",
                "main_photo_file_id": render.main_photo_file_id,
                "main_photo_caption": render.main_photo_caption or "",
                "main_photo_caption_entities": render.main_photo_caption_entities,
            }
        )
    else:
        draft.update(
            {
                "main_content_type": "text",
                "main_text": render.main_text or "",
                "main_entities": render.main_entities,
            }
        )

    if render.extra_document_file_id:
        draft.update(
            {
                "extra_document_file_id": render.extra_document_file_id,
                "extra_document_caption": render.extra_document_caption or "",
                "extra_document_caption_entities": render.extra_document_caption_entities,
            }
        )

    await state.set_state(PageEditingStates.waiting_for_content)
    await state.update_data(page_draft=draft)
    await message.answer(
        f"Редактирование страницы {page_key}. Пришли текст, фото или документ.\n"
        "После каждого обновления я автоматически покажу превью.\n"
        "Чтобы выйти без сохранения, нажми «❌ Отмена».",
        reply_markup=page_draft_cancel_keyboard(),
    )




@router.callback_query(F.data.startswith(EDIT_PAGE_CALLBACK_PREFIX))
async def edit_page_callback(callback: CallbackQuery, state: FSMContext) -> None:
    is_admin = _is_admin(callback)
    user_id = callback.from_user.id if callback.from_user else None
    logger.info("PAGE_EDIT_CLICK user_id=%s is_admin=%s", user_id, is_admin)
    if not is_admin:
        await callback.answer("Недостаточно прав")
        return
    data = callback.data or ""
    page_key = data[len(EDIT_PAGE_CALLBACK_PREFIX) :]
    if page_key not in PAGE_KEYS:
        await callback.answer("Недоступная страница")
        return

    await callback.answer()
    if callback.message:
        await _start_page_editing(
            callback.message,
            state,
            page_key,
            user_id=user_id,
            username=callback.from_user.username if callback.from_user else None,
        )


@router.message(Command("edit_faq"))
async def edit_faq_command(message: Message, state: FSMContext) -> None:
    await _start_page_editing(message, state, PAGE_KEY_FAQ)


@router.message(Command("edit_contacts"))
async def edit_contacts_command(message: Message, state: FSMContext) -> None:
    await _start_page_editing(message, state, PAGE_KEY_CONTACTS)


@router.message(Command("edit_schedule"))
async def edit_schedule_command(message: Message, state: FSMContext) -> None:
    await _start_page_editing(message, state, PAGE_KEY_SCHEDULE)


@router.message(Command("edit_photo"))
async def edit_photo_command(message: Message, state: FSMContext) -> None:
    await _start_page_editing(message, state, PAGE_KEY_PHOTO)


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
            if _should_send_album_warning(message):
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

    is_document_update = bool(message.document)
    if is_document_update and not result.notice:
        return

    await service.send_preview(message.bot, message.chat.id, result.post)
    if result.notice:
        await message.answer(result.notice)
        return
    await message.answer("Черновик обновлён.", reply_markup=post_confirm_keyboard())


@router.message(
    StateFilter(PostCreationStates.waiting_for_content),
    F.text,
)
async def post_text_handler(message: Message) -> None:
    if not _is_admin(message):
        return
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
async def post_media_handler(message: Message) -> None:
    if not _is_admin(message):
        return
    await _handle_post_content(message)


@router.message(StateFilter(PostCreationStates.waiting_for_content))
async def post_unsupported_handler(message: Message) -> None:
    if not _is_admin(message):
        return
    if message.media_group_id:
        if _should_send_album_warning(message):
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
    if not _is_admin(callback) or callback.from_user is None:
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
    if not _is_admin(callback) or callback.from_user is None:
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
    if not _is_admin(callback) or callback.from_user is None:
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
    if not _is_admin(callback) or callback.from_user is None:
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


async def _send_page_draft_preview(message: Message, page_key: str, draft: dict) -> None:
    reply_markup = page_edit_keyboard(page_key)

    if draft.get("main_content_type") == "photo" and draft.get("main_photo_file_id"):
        await message.answer_photo(
            draft["main_photo_file_id"],
            caption=draft.get("main_photo_caption") or "",
            caption_entities=draft.get("main_photo_caption_entities"),
            reply_markup=reply_markup,
        )
    else:
        text = (draft.get("main_text") or "").strip()
        if text:
            await message.answer(
                text,
                entities=draft.get("main_entities"),
                reply_markup=reply_markup,
            )
        elif draft.get("extra_document_file_id"):
            await message.answer(
                "Основной контент пока не задан.",
                reply_markup=reply_markup,
            )
        else:
            await message.answer(DEFAULT_PAGE_MESSAGE, reply_markup=reply_markup)

    if draft.get("extra_document_file_id"):
        await message.answer_document(
            draft["extra_document_file_id"],
            caption=draft.get("extra_document_caption") or "",
            caption_entities=draft.get("extra_document_caption_entities"),
        )


@router.message(
    StateFilter(PageEditingStates.waiting_for_content),
    F.text & ~F.text.startswith("/"),
)
async def handle_page_editing_text(message: Message, state: FSMContext) -> None:
    if not _is_admin(message) or message.from_user is None:
        return

    current_state = await state.get_state()
    logger.info(
        "PAGE_TEXT_HANDLER hit state=%s user_id=%s prefix=%r",
        current_state,
        message.from_user.id,
        (message.text or "")[:30],
    )

    service = PageEditingService(
        session_maker=message.bot.session_maker,
        user_repository=UserRepository(),
    )
    editing_key = await service.get_editing_key(message.from_user.id)
    if editing_key is None:
        return

    data = await state.get_data()
    draft = dict(data.get("page_draft") or {})
    draft.update(
        {
            "key": editing_key,
            "main_content_type": "text",
            "main_text": message.text,
            "main_entities": message.entities,
        }
    )

    await state.update_data(page_draft=draft)
    await _send_page_draft_preview(message, editing_key, draft)
    await message.answer("Черновик обновлён.", reply_markup=page_draft_confirm_keyboard())


@router.message(
    StateFilter(PageEditingStates.waiting_for_content),
    F.photo | F.document,
)
async def handle_page_editing_media(message: Message, state: FSMContext) -> None:
    if not _is_admin(message) or message.from_user is None:
        return

    service = PageEditingService(
        session_maker=message.bot.session_maker,
        user_repository=UserRepository(),
    )
    editing_key = await service.get_editing_key(message.from_user.id)
    if editing_key is None:
        return

    data = await state.get_data()
    draft = dict(data.get("page_draft") or {})
    draft["key"] = editing_key

    if message.media_group_id:
        if _should_send_album_warning(message):
            await message.answer(
                "Альбомы не поддерживаются. Пришли одно фото/видео/гиф одним сообщением.",
                reply_markup=page_draft_confirm_keyboard(),
            )
        return

    should_respond = True
    if message.photo:
        draft.update(
            {
                "main_content_type": "photo",
                "main_photo_file_id": message.photo[-1].file_id,
                "main_photo_caption": message.caption or "",
                "main_photo_caption_entities": message.caption_entities,
            }
        )
    elif message.document:
        draft.update(
            {
                "extra_document_file_id": message.document.file_id,
                "extra_document_caption": message.caption or "",
                "extra_document_caption_entities": message.caption_entities,
            }
        )
        should_respond = _is_document_notice_allowed(message)

    await state.update_data(page_draft=draft)
    if not should_respond:
        return

    await _send_page_draft_preview(message, editing_key, draft)
    if message.document:
        await message.answer(
            "Файл заменён. Он будет отправлен отдельным сообщением.",
            reply_markup=page_draft_confirm_keyboard(),
        )
        return
    await message.answer("Черновик обновлён.", reply_markup=page_draft_confirm_keyboard())


@router.message(StateFilter(PageEditingStates.waiting_for_content))
async def handle_page_editing_unsupported(message: Message) -> None:
    if not _is_admin(message):
        return
    if message.media_group_id:
        if _should_send_album_warning(message):
            await message.answer(
                "Альбомы не поддерживаются. Пришли одно фото/видео/гиф одним сообщением.",
                reply_markup=page_draft_confirm_keyboard(),
            )
        return
    await message.answer("Пока поддерживаются: текст, фото, документ.")


@router.callback_query(F.data == PAGE_DRAFT_SAVE_CALLBACK)
async def save_page_draft_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback) or callback.from_user is None:
        await callback.answer("Недостаточно прав")
        return

    service = PageEditingService(
        session_maker=callback.bot.session_maker,
        user_repository=UserRepository(),
    )
    editing_key = await service.get_editing_key(callback.from_user.id)
    if editing_key is None:
        await callback.answer("Черновик не найден", show_alert=True)
        return

    data = await state.get_data()
    draft = dict(data.get("page_draft") or {})
    if not draft:
        await callback.answer("Черновик пуст", show_alert=True)
        return

    page_service = PageService(
        session_maker=callback.bot.session_maker,
        page_repository=PageRepository(),
    )
    if draft.get("main_content_type") == "photo" and draft.get("main_photo_file_id"):
        await page_service.update_page_photo(
            editing_key,
            file_id=draft["main_photo_file_id"],
            caption=draft.get("main_photo_caption"),
            caption_entities=serialize_entities(draft.get("main_photo_caption_entities")),
        )
    else:
        await page_service.update_page_text(
            editing_key,
            text=draft.get("main_text") or "",
            entities=serialize_entities(draft.get("main_entities")),
        )

    if draft.get("extra_document_file_id"):
        await page_service.update_page_document(
            editing_key,
            file_id=draft["extra_document_file_id"],
            caption=draft.get("extra_document_caption"),
            caption_entities=serialize_entities(draft.get("extra_document_caption_entities")),
        )

    await service.cancel_editing(callback.from_user.id)
    await state.clear()
    await callback.answer()
    if callback.message:
        await callback.message.answer("✅ Сохранено.")


@router.callback_query(F.data == PAGE_DRAFT_CANCEL_CALLBACK)
async def cancel_page_draft_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback) or callback.from_user is None:
        await callback.answer("Недостаточно прав")
        return

    service = PageEditingService(
        session_maker=callback.bot.session_maker,
        user_repository=UserRepository(),
    )
    await service.cancel_editing(callback.from_user.id)
    await state.clear()
    await callback.answer()
    if callback.message:
        await callback.message.answer("Отменено")

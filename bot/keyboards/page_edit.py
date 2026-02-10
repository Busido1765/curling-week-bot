from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

EDIT_PAGE_CALLBACK_PREFIX = "edit_page:"
PAGE_DRAFT_SAVE_CALLBACK = "page_draft_save"
PAGE_DRAFT_CANCEL_CALLBACK = "page_draft_cancel"
PAGE_DRAFT_DELETE_DOC_CALLBACK = "page_draft_delete_doc"


def page_edit_keyboard(page_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Редактировать",
                    callback_data=f"{EDIT_PAGE_CALLBACK_PREFIX}{page_key}",
                )
            ]
        ]
    )


def page_draft_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=PAGE_DRAFT_CANCEL_CALLBACK,
                )
            ]
        ]
    )


def page_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Сохранить",
                    callback_data=PAGE_DRAFT_SAVE_CALLBACK,
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=PAGE_DRAFT_CANCEL_CALLBACK,
                )
            ],
        ]
    )


def page_draft_delete_document_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Удалить файл",
                    callback_data=PAGE_DRAFT_DELETE_DOC_CALLBACK,
                )
            ]
        ]
    )

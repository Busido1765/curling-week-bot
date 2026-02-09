from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

EDIT_PAGE_CALLBACK_PREFIX = "edit_page:"


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

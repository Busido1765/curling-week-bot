from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

POST_PREVIEW_CALLBACK = "post_preview"
POST_SEND_CALLBACK = "post_send"
POST_CLEAR_CALLBACK = "post_clear"
POST_CANCEL_CALLBACK = "post_cancel"


def post_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=POST_CANCEL_CALLBACK,
                )
            ]
        ]
    )


def post_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Отправить всем",
                    callback_data=POST_SEND_CALLBACK,
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=POST_CANCEL_CALLBACK,
                ),
            ]
        ]
    )

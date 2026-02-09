from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

POST_SEND_CALLBACK_PREFIX = "post_send:"
POST_CANCEL_CALLBACK_PREFIX = "post_cancel:"


def post_confirm_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Отправить всем",
                    callback_data=f"{POST_SEND_CALLBACK_PREFIX}{post_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"{POST_CANCEL_CALLBACK_PREFIX}{post_id}",
                ),
            ]
        ]
    )

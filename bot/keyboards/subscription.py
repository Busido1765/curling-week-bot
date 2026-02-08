from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CHECK_SUBSCRIPTION_CALLBACK = "check_subscription"


def subscription_check_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Проверить подписку",
                    callback_data=CHECK_SUBSCRIPTION_CALLBACK,
                )
            ]
        ]
    )

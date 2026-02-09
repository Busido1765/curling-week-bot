from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CHECK_SUBSCRIPTION_CALLBACK = "check_subscription"


def subscription_check_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить подписку",
                    callback_data=CHECK_SUBSCRIPTION_CALLBACK,
                )
            ]
        ]
    )


def subscription_links_keyboard(
    links: Sequence[tuple[str, str]]
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=title, url=url)] for title, url in links
        ]
    )

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BACK_BUTTON = "◀️ Назад"


def back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BACK_BUTTON)]],
        resize_keyboard=True,
    )

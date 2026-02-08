from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

SCHEDULE_BUTTON = "📅 Расписание"
FAQ_BUTTON = "❓ FAQ"
CONTACTS_BUTTON = "📩 Контакты"
PHOTO_BUTTON = "🖼 Фото"


def confirmed_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=SCHEDULE_BUTTON), KeyboardButton(text=FAQ_BUTTON)],
            [KeyboardButton(text=CONTACTS_BUTTON), KeyboardButton(text=PHOTO_BUTTON)],
        ],
        resize_keyboard=True,
    )

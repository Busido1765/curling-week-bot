from aiogram.types import CallbackQuery, Message


def is_admin_user_id(user_id: int | None, admin_ids: set[int]) -> bool:
    if user_id is None:
        return False
    return user_id in admin_ids


def is_admin_event(event: Message | CallbackQuery) -> bool:
    user_id = event.from_user.id if event.from_user else None
    return is_admin_user_id(user_id, event.bot.settings.admin_ids)

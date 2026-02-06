from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message


router = Router()


@router.message(Command("admin"))
async def admin_menu(message: Message) -> None:
    settings = message.bot["settings"]
    if message.from_user is None or message.from_user.id not in settings.admin_ids:
        await message.answer("Access denied")
        return
    await message.answer("Admin menu is under construction")

import logging
from typing import Iterable

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from bot.config import Settings

logger = logging.getLogger(__name__)


def _unique_admin_ids(admin_ids: Iterable[int]) -> list[int]:
    unique_ids: list[int] = []
    seen = set()
    for admin_id in admin_ids:
        if admin_id in seen:
            continue
        seen.add(admin_id)
        unique_ids.append(admin_id)
    return unique_ids


async def setup_bot_commands(bot: Bot, settings: Settings) -> None:
    """Configure bot commands for public users and admins.

    Note: Telegram may cache the command list; after updates, reopen the chat
    with the bot or send /start to refresh the menu.
    """
    default_commands = [
        BotCommand(command="start", description="Начать"),
    ]
    try:
        await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())
    except Exception:
        logger.warning("Failed to set default bot commands", exc_info=True)

    admin_commands = [
        BotCommand(command="start", description="Начать"),
        BotCommand(command="post", description="Новый анонс"),
    ]
    for admin_id in _unique_admin_ids(settings.admin_ids):
        try:
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except Exception:
            logger.warning(
                "Failed to set admin commands for chat_id=%s", admin_id, exc_info=True
            )

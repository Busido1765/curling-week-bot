import asyncio
import logging

from aiogram import Bot

from bot.config import load_settings
from bot.db.session import create_sessionmaker
from bot.dispatcher import setup_dispatcher


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()

    engine, session_maker = create_sessionmaker(settings)

    bot = Bot(token=settings.bot_token)
    bot.settings = settings
    bot.engine = engine
    bot.session_maker = session_maker

    dispatcher = setup_dispatcher()
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

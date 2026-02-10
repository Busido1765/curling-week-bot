from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import admin, common, user


def setup_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(admin.router)
    dispatcher.include_router(common.router)
    dispatcher.include_router(user.router)
    return dispatcher

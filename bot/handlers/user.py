import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.services.registration import RegistrationService
from bot.services.token_verifier import get_token_verifier
from bot.storage import UserRepository

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def start_handler(message: Message) -> None:
    token = None
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            token = parts[1]

    tg_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None
    logger.info("Received /start tg_id=%s token_provided=%s", tg_id, token is not None)

    service = RegistrationService(
        session_maker=message.bot.session_maker,
        user_repository=UserRepository(),
        token_verifier=get_token_verifier(),
    )
    result = await service.handle_start(tg_id=tg_id, username=username, token=token)

    if not result.token_provided:
        await message.answer(
            "Нужна регистрация на сайте. После регистрации открой ссылку, которая приведёт в бот"
        )
        return

    if result.token_valid:
        await message.answer(
            "Токен принят. Следующий шаг — проверка подписки на канал (будет в следующей итерации)"
        )
        return

    await message.answer("Токен неверный/просрочен")

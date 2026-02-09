import sys
import unittest
from pathlib import Path

from aiogram.filters import CommandStart
from aiogram.types import Message

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.filters import Command


class DummyBot:
    async def me(self):
        class BotInfo:
            username = "testbot"

        return BotInfo()


def make_message(text: str) -> Message:
    return Message.model_validate(
        {
            "message_id": 1,
            "date": 0,
            "chat": {"id": 1, "type": "private"},
            "from": {"id": 1, "is_bot": False, "first_name": "Test"},
            "text": text,
        }
    )


class TestCommandFilters(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.bot = DummyBot()

    async def test_start_command_matches(self) -> None:
        result = await CommandStart()(make_message("/start"), self.bot)
        self.assertTrue(result)

    async def test_start_command_matches_with_payload(self) -> None:
        result = await CommandStart()(make_message("/start TEST"), self.bot)
        self.assertTrue(result)

    async def test_start_command_not_match_other(self) -> None:
        result = await CommandStart()(make_message("/startXYZ"), self.bot)
        self.assertFalse(result)

    async def test_non_command_filter_blocks_commands(self) -> None:
        non_command_filter = ~Command()
        self.assertFalse(await non_command_filter(make_message("/start"), self.bot))
        self.assertFalse(await non_command_filter(make_message("/cancel"), self.bot))
        self.assertTrue(await non_command_filter(make_message("hello"), self.bot))

    async def test_start_handler_filter_present_in_dispatcher(self) -> None:
        from bot.dispatcher import setup_dispatcher

        dispatcher = setup_dispatcher()
        start_handlers = []
        for router in dispatcher.sub_routers:
            for handler in router.message.handlers:
                if handler.callback.__name__ == "start_handler":
                    start_handlers.append(handler)

        self.assertEqual(len(start_handlers), 1)
        start_filter = start_handlers[0].filters[0].callback
        self.assertTrue(await start_filter(make_message("/start"), self.bot))

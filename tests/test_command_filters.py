import re
import unittest

from aiogram.filters import Command, CommandStart
from aiogram.types import Message


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
        non_command_filter = ~Command(re.compile(r".+"))
        self.assertFalse(await non_command_filter(make_message("/start"), self.bot))
        self.assertTrue(await non_command_filter(make_message("hello"), self.bot))

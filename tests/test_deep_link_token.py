import unittest

from aiogram.utils.deep_linking import create_start_link

from bot.utils.deep_link import extract_start_token


class DummyBot:
    async def me(self):
        class BotInfo:
            username = "testbot"

        return BotInfo()


class TestExtractStartToken(unittest.IsolatedAsyncioTestCase):
    async def test_returns_raw_jwt_from_command_args(self) -> None:
        token = "a.b.c"
        self.assertEqual(extract_start_token("/start a.b.c", token), token)

    async def test_decodes_base64url_payload(self) -> None:
        bot = DummyBot()
        jwt = "header.payload.signature"
        start_link = await create_start_link(bot, jwt, encode=True)
        encoded = start_link.split("start=", maxsplit=1)[1]

        self.assertEqual(extract_start_token(f"/start {encoded}", encoded), jwt)

    async def test_fallback_to_message_text_when_args_empty(self) -> None:
        token = "a.b.c"
        self.assertEqual(extract_start_token(f"/start {token}", None), token)

    async def test_empty_payload_returns_none(self) -> None:
        self.assertIsNone(extract_start_token("/start   ", "   "))

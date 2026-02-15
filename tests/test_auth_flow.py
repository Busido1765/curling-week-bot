import base64
import hashlib
import hmac
import json
import time
import unittest

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.models import RegistrationStatus
from bot.services.registration import RegistrationService
from bot.services.token_verifier import get_token_verifier


class FakeUser:
    def __init__(self, tg_id: int, username: str | None, status: RegistrationStatus) -> None:
        self.tg_id = tg_id
        self.username = username
        self.status = status


class FakeUserRepository:
    def __init__(self) -> None:
        self._users: dict[int, FakeUser] = {}

    async def get_by_tg_id(self, session, tg_id: int):
        return self._users.get(tg_id)

    async def create(self, session, tg_id: int, username: str | None, status: RegistrationStatus):
        user = FakeUser(tg_id=tg_id, username=username, status=status)
        self._users[tg_id] = user
        return user

    async def update_username(self, session, user: FakeUser, username: str | None) -> None:
        user.username = username

    async def set_status(self, session, user: FakeUser, status: RegistrationStatus) -> None:
        user.status = status


class _Ctx:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def begin(self):
        return _Ctx()


class FakeSessionMaker:
    def __call__(self):
        return _Ctx()


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_token(secret: str, payload: dict[str, object] | None = None) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    default_payload = {
        "sub": "site-user-1",
        "iat": now,
        "exp": now + 300,
        "aud": "curling-week-bot",
    }
    if payload:
        default_payload.update(payload)

    encoded_header = b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = b64url(json.dumps(default_payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    encoded_signature = b64url(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


class TestJwtTokenVerifier(unittest.TestCase):
    def test_valid_token(self) -> None:
        verifier = get_token_verifier("secret")
        token = make_token("secret")
        self.assertTrue(verifier.is_valid(token))

    def test_invalid_audience(self) -> None:
        verifier = get_token_verifier("secret")
        token = make_token("secret", payload={"aud": "other-service"})
        self.assertFalse(verifier.is_valid(token))

    def test_missing_required_claim(self) -> None:
        verifier = get_token_verifier("secret")
        token = make_token("secret")
        parts = token.split(".")
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode("utf-8"))
        payload.pop("aud", None)
        tampered_payload = b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{parts[0]}.{tampered_payload}".encode("utf-8")
        signature = b64url(hmac.new(b"secret", signing_input, hashlib.sha256).digest())
        bad_token = f"{parts[0]}.{tampered_payload}.{signature}"
        self.assertFalse(verifier.is_valid(bad_token))


class TestRegistrationAdminBypass(unittest.IsolatedAsyncioTestCase):
    async def test_non_admin_without_token_is_rejected(self) -> None:
        service = RegistrationService(
            session_maker=FakeSessionMaker(),
            user_repository=FakeUserRepository(),
            token_verifier=get_token_verifier("secret"),
            admin_ids=[42],
        )
        result = await service.handle_start(tg_id=100, username="user", token=None)
        self.assertFalse(result.token_provided)
        self.assertIsNone(result.token_valid)
        self.assertEqual(result.current_status, RegistrationStatus.NONE)

    async def test_admin_without_token_is_allowed(self) -> None:
        service = RegistrationService(
            session_maker=FakeSessionMaker(),
            user_repository=FakeUserRepository(),
            token_verifier=get_token_verifier("secret"),
            admin_ids=[42],
        )
        result = await service.handle_start(tg_id=42, username="admin", token=None)
        self.assertTrue(result.token_provided)
        self.assertTrue(result.token_valid)
        self.assertEqual(result.current_status, RegistrationStatus.TOKEN_VERIFIED)

    async def test_regular_user_with_valid_token_is_allowed(self) -> None:
        service = RegistrationService(
            session_maker=FakeSessionMaker(),
            user_repository=FakeUserRepository(),
            token_verifier=get_token_verifier("secret"),
            admin_ids=[42],
        )
        token = make_token("secret")
        result = await service.handle_start(tg_id=100, username="user", token=token)
        self.assertTrue(result.token_provided)
        self.assertTrue(result.token_valid)
        self.assertEqual(result.current_status, RegistrationStatus.TOKEN_VERIFIED)

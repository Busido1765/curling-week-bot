import base64
import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.models import RegistrationStatus
from bot.services.registration import RegistrationService
from bot.services.token_verifier import get_token_verifier


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


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


class RsaTokenFactory:
    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)
        self.private_key_path = self._tmp_path / "private.pem"
        self.public_key_path = self._tmp_path / "public.pem"

        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:2048",
                "-out",
                str(self.private_key_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "openssl",
                "rsa",
                "-pubout",
                "-in",
                str(self.private_key_path),
                "-out",
                str(self.public_key_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    def close(self) -> None:
        self._tmp.cleanup()

    def public_key_pem(self) -> str:
        return self.public_key_path.read_text()

    def make_token(self, payload: dict[str, object] | None = None, alg: str = "RS256") -> str:
        now = int(time.time())
        header = {"alg": alg, "typ": "JWT"}
        body = {
            "sub": "site-user-1",
            "iat": now,
            "exp": now + 300,
            "aud": "curling-week-bot",
        }
        if payload:
            body.update(payload)

        encoded_header = b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        encoded_payload = b64url(json.dumps(body, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")

        data_path = self._tmp_path / "jwt_data.bin"
        sig_path = self._tmp_path / "jwt_sig.bin"
        data_path.write_bytes(signing_input)

        subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-sign",
                str(self.private_key_path),
                "-out",
                str(sig_path),
                str(data_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        encoded_signature = b64url(sig_path.read_bytes())
        return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


class TestJwtTokenVerifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.factory = RsaTokenFactory()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.factory.close()

    def test_valid_token(self) -> None:
        verifier = get_token_verifier(self.factory.public_key_pem())
        token = self.factory.make_token()
        self.assertTrue(verifier.is_valid(token))

    def test_invalid_audience(self) -> None:
        verifier = get_token_verifier(self.factory.public_key_pem())
        token = self.factory.make_token(payload={"aud": "other-service"})
        self.assertFalse(verifier.is_valid(token))

    def test_missing_required_claim(self) -> None:
        verifier = get_token_verifier(self.factory.public_key_pem())
        token = self.factory.make_token()
        header_b64, payload_b64, _ = token.split(".")
        payload = json.loads(b64url_decode(payload_b64).decode("utf-8"))
        payload.pop("aud", None)

        tampered_payload_b64 = b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{header_b64}.{tampered_payload_b64}".encode("utf-8")

        data_path = self.factory._tmp_path / "tampered_data.bin"
        sig_path = self.factory._tmp_path / "tampered_sig.bin"
        data_path.write_bytes(signing_input)
        subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-sign",
                str(self.factory.private_key_path),
                "-out",
                str(sig_path),
                str(data_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        bad_token = f"{header_b64}.{tampered_payload_b64}.{b64url(sig_path.read_bytes())}"
        self.assertFalse(verifier.is_valid(bad_token))

    def test_rejects_non_rs256_header(self) -> None:
        verifier = get_token_verifier(self.factory.public_key_pem())
        token = self.factory.make_token(alg="HS256")
        self.assertFalse(verifier.is_valid(token))


class TestRegistrationAdminBypass(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.factory = RsaTokenFactory()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.factory.close()

    async def test_non_admin_without_token_is_rejected(self) -> None:
        service = RegistrationService(
            session_maker=FakeSessionMaker(),
            user_repository=FakeUserRepository(),
            token_verifier=get_token_verifier(self.factory.public_key_pem()),
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
            token_verifier=get_token_verifier(self.factory.public_key_pem()),
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
            token_verifier=get_token_verifier(self.factory.public_key_pem()),
            admin_ids=[42],
        )
        token = self.factory.make_token()
        result = await service.handle_start(tg_id=100, username="user", token=token)
        self.assertTrue(result.token_provided)
        self.assertTrue(result.token_valid)
        self.assertEqual(result.current_status, RegistrationStatus.TOKEN_VERIFIED)

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time

logger = logging.getLogger(__name__)


class TokenVerifier:
    def is_valid(self, token: str) -> bool:
        raise NotImplementedError


class JwtHs256TokenVerifier(TokenVerifier):
    def __init__(self, secret: str, audience: str = "curling-week-bot") -> None:
        self._secret = secret.encode("utf-8")
        self._audience = audience

    def is_valid(self, token: str) -> bool:
        try:
            header_b64, payload_b64, signature_b64 = token.split(".")
        except ValueError:
            return False

        try:
            header = self._decode_json(header_b64)
            payload = self._decode_json(payload_b64)
        except (json.JSONDecodeError, ValueError):
            return False

        if header.get("alg") != "HS256":
            return False

        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_signature = hmac.new(
            self._secret,
            signing_input,
            hashlib.sha256,
        ).digest()
        actual_signature = self._b64url_decode(signature_b64)
        if not hmac.compare_digest(expected_signature, actual_signature):
            return False

        if not self._has_required_claims(payload):
            return False

        now = int(time.time())
        try:
            exp = int(payload["exp"])
            iat = int(payload["iat"])
        except (TypeError, ValueError):
            return False

        if exp <= now:
            return False
        if iat > now + 60:
            return False

        aud = payload.get("aud")
        if isinstance(aud, str):
            return aud == self._audience
        if isinstance(aud, list):
            return self._audience in aud
        return False

    @staticmethod
    def _has_required_claims(payload: dict[str, object]) -> bool:
        return all(key in payload for key in ("sub", "exp", "iat", "aud"))

    @staticmethod
    def _decode_json(data: str) -> dict[str, object]:
        decoded = JwtHs256TokenVerifier._b64url_decode(data)
        as_json = json.loads(decoded.decode("utf-8"))
        if not isinstance(as_json, dict):
            raise ValueError("JWT part is not JSON object")
        return as_json

    @staticmethod
    def _b64url_decode(data: str) -> bytes:
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + padding)


def get_token_verifier(jwt_secret: str) -> TokenVerifier:
    return JwtHs256TokenVerifier(secret=jwt_secret)

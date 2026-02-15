from __future__ import annotations

import base64
import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class TokenVerifier:
    def is_valid(self, token: str) -> bool:
        raise NotImplementedError


class JwtRs256TokenVerifier(TokenVerifier):
    def __init__(self, public_key_pem: str, audience: str = "curling-week-bot") -> None:
        normalized = public_key_pem.replace("\\n", "\n").strip()
        self._public_key_pem = normalized
        self._audience = audience

    def is_valid(self, token: str) -> bool:
        if not self._public_key_pem:
            logger.warning("JWT public key is empty")
            return False

        try:
            header_b64, payload_b64, signature_b64 = token.split(".")
        except ValueError:
            return False

        try:
            header = self._decode_json(header_b64)
            payload = self._decode_json(payload_b64)
            signature = self._b64url_decode(signature_b64)
        except (json.JSONDecodeError, ValueError):
            return False

        if header.get("alg") != "RS256":
            return False

        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        if not self._verify_signature(signing_input, signature):
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

    def _verify_signature(self, signing_input: bytes, signature: bytes) -> bool:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            data_path = tmp_path / "jwt_data.bin"
            signature_path = tmp_path / "jwt_signature.bin"
            key_path = tmp_path / "jwt_public_key.pem"

            data_path.write_bytes(signing_input)
            signature_path.write_bytes(signature)
            key_path.write_text(self._public_key_pem)

            result = subprocess.run(
                [
                    "openssl",
                    "dgst",
                    "-sha256",
                    "-verify",
                    str(key_path),
                    "-signature",
                    str(signature_path),
                    str(data_path),
                ],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0

    @staticmethod
    def _has_required_claims(payload: dict[str, object]) -> bool:
        return all(key in payload for key in ("sub", "exp", "iat", "aud"))

    @staticmethod
    def _decode_json(data: str) -> dict[str, object]:
        decoded = JwtRs256TokenVerifier._b64url_decode(data)
        as_json = json.loads(decoded.decode("utf-8"))
        if not isinstance(as_json, dict):
            raise ValueError("JWT part is not JSON object")
        return as_json

    @staticmethod
    def _b64url_decode(data: str) -> bytes:
        padding = "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data + padding)


def get_token_verifier(jwt_public_key: str) -> TokenVerifier:
    return JwtRs256TokenVerifier(public_key_pem=jwt_public_key)

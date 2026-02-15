from __future__ import annotations

from aiogram.utils.deep_linking import decode_payload


def extract_start_token(message_text: str | None, command_args: str | None) -> str | None:
    token = command_args
    if token is None and message_text:
        parts = message_text.split(maxsplit=1)
        if len(parts) > 1:
            token = parts[1]

    if token is None:
        return None

    token = token.strip()
    if not token:
        return None

    if "." in token:
        return token

    try:
        decoded = decode_payload(token)
    except Exception:
        return token

    decoded = decoded.strip()
    return decoded or None

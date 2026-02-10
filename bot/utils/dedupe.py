from __future__ import annotations

import time

_ALBUM_TTL_SECONDS = 10.0
_DOCUMENT_NOTICE_TTL_SECONDS = 5.0

_seen_media_groups: dict[tuple[int, str], float] = {}
_seen_document_notices: dict[tuple[int, int], float] = {}


def _cleanup(cache: dict[tuple[int, ...] | tuple[int, str], float], ttl_seconds: float, now: float) -> None:
    expired_keys = [key for key, ts in cache.items() if now - ts >= ttl_seconds]
    for key in expired_keys:
        cache.pop(key, None)


def should_notify_album(chat_id: int, media_group_id: str, ttl_seconds: float = _ALBUM_TTL_SECONDS) -> bool:
    now = time.monotonic()
    _cleanup(_seen_media_groups, ttl_seconds, now)
    key = (chat_id, media_group_id)
    last_seen = _seen_media_groups.get(key)
    if last_seen is not None and now - last_seen < ttl_seconds:
        return False
    _seen_media_groups[key] = now
    return True


def should_notify_document_update(
    chat_id: int,
    user_id: int,
    ttl_seconds: float = _DOCUMENT_NOTICE_TTL_SECONDS,
) -> bool:
    now = time.monotonic()
    _cleanup(_seen_document_notices, ttl_seconds, now)
    key = (chat_id, user_id)
    last_seen = _seen_document_notices.get(key)
    if last_seen is not None and now - last_seen < ttl_seconds:
        return False
    _seen_document_notices[key] = now
    return True


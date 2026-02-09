from __future__ import annotations

from aiogram.types import MessageEntity


def serialize_entities(entities: list[MessageEntity] | None) -> list[dict] | None:
    if not entities:
        return None
    return [entity.model_dump(exclude_none=True) for entity in entities]


def deserialize_entities(raw_entities: list[dict] | None) -> list[MessageEntity] | None:
    if not raw_entities:
        return None
    return [MessageEntity.model_validate(entity) for entity in raw_entities]

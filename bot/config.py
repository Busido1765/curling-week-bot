# bot/config.py
from __future__ import annotations

import json
import logging
from typing import Any, List

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class RequiredChannel(BaseModel):
    id: int
    title: str = ""
    url: str = ""


class Settings(BaseSettings):
    bot_token: str
    database_url: str
    jwt_public_key: str
    admin_ids: List[int]
    required_channels: List[RequiredChannel] = Field(
        default_factory=list,
        validation_alias="REQUIRED_CHANNELS",
    )
    broadcast_delay_seconds: float = Field(
        default=0.07,
        validation_alias="BROADCAST_DELAY_SECONDS",
    )
    broadcast_batch_log_every: int = Field(
        default=50,
        validation_alias="BROADCAST_BATCH_LOG_EVERY",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _split_admin_ids(cls, value: Any) -> List[int]:
        """
        CHANGED:
        Раньше value ожидался как str | List[int] и код делал value.split(",").
        Но иногда value приходит как int (например ADMIN_IDS=12345),
        и тогда split() падал с: AttributeError: 'int' object has no attribute 'split'.

        Теперь валидатор принимает Any и корректно обрабатывает:
        - None / "" -> []
        - int -> [int]
        - list -> [int, int, ...]
        - str -> "1,2,3" -> [1,2,3]
        - всё остальное -> приводим к строке и парсим как CSV
        """
        # CHANGED: безопасная обработка пустых значений
        if value is None or value == "":
            return []

        # CHANGED: если пришло одно число (самый частый кейс твоей ошибки)
        if isinstance(value, int):
            return [value]

        # CHANGED: если уже список (например [1,2] или ["1","2"])
        if isinstance(value, list):
            return [int(x) for x in value]

        # CHANGED: строка или что-то приводимое к строке
        s = str(value)
        return [int(item.strip()) for item in s.split(",") if item.strip()]

    @field_validator("required_channels", mode="before")
    @classmethod
    def _parse_required_channels(cls, value: Any) -> List[RequiredChannel]:
        if value is None:
            return []
        if value == "":
            logger.warning("REQUIRED_CHANNELS is empty")
            return []

        parsed: Any
        if isinstance(value, list):
            parsed = value
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Invalid REQUIRED_CHANNELS JSON")
                return []
        else:
            logger.warning("Unexpected REQUIRED_CHANNELS format")
            return []

        if not isinstance(parsed, list):
            logger.warning("REQUIRED_CHANNELS is not a list")
            return []

        channels: List[RequiredChannel] = []
        for item in parsed:
            if isinstance(item, RequiredChannel):
                channels.append(item)
                continue
            if not isinstance(item, dict):
                logger.warning("Invalid REQUIRED_CHANNELS item skipped: %s", item)
                continue
            raw_id = item.get("id")
            try:
                channel_id = int(raw_id)
            except (TypeError, ValueError):
                logger.warning("Invalid REQUIRED_CHANNELS id skipped: %s", raw_id)
                continue
            title = item.get("title")
            url = item.get("url")
            channels.append(
                RequiredChannel(
                    id=channel_id,
                    title=str(title).strip() if title is not None else "",
                    url=str(url).strip() if url is not None else "",
                )
            )

        return channels

def load_settings() -> Settings:
    return Settings()

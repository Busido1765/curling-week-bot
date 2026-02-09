# bot/config.py
from __future__ import annotations

import json
from typing import Any, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str
    jwt_secret: str
    admin_ids: List[int]
    required_channel_ids: List[int] = Field(
        default_factory=list,
        validation_alias="REQUIRED_CHANNEL_IDS",
    )
    required_channel_links: List[str] = Field(
        default_factory=list,
        validation_alias="REQUIRED_CHANNEL_LINKS",
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

    @field_validator("required_channel_ids", mode="before")
    @classmethod
    def _parse_required_channel_ids(cls, value: Any) -> List[int]:
        if value is None or value == "":
            return []

        if isinstance(value, int):
            return [value]

        if isinstance(value, list):
            return [int(item) for item in value]

        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("[") and raw.endswith("]"):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
                else:
                    if isinstance(parsed, list):
                        return [int(item) for item in parsed]
            if "," in raw:
                return [int(item.strip()) for item in raw.split(",") if item.strip()]
            if raw:
                return [int(raw)]

        return [int(item) for item in str(value).split(",") if str(item).strip()]

    @field_validator("required_channel_links", mode="before")
    @classmethod
    def _parse_required_channel_links(cls, value: Any) -> List[str]:
        if value is None or value == "":
            return []

        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]

        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("[") and raw.endswith("]"):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = None
                else:
                    if isinstance(parsed, list):
                        return [
                            str(item).strip() for item in parsed if str(item).strip()
                        ]
            if "," in raw:
                return [item.strip() for item in raw.split(",") if item.strip()]
            if raw:
                return [raw]

        return [str(item).strip() for item in str(value).split(",") if str(item).strip()]


def load_settings() -> Settings:
    return Settings()

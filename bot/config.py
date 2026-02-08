# bot/config.py
from __future__ import annotations

from typing import Any, List  # CHANGED: добавили Any, чтобы валидатор принимал int/str/list без падений

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    database_url: str
    jwt_secret: str
    admin_ids: List[int]
    required_channel_id: int

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


def load_settings() -> Settings:
    return Settings()

from __future__ import annotations

from typing import List

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
    def _split_admin_ids(cls, value: str | List[int]) -> List[int]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [int(item.strip()) for item in value.split(",") if item.strip()]


def load_settings() -> Settings:
    return Settings()

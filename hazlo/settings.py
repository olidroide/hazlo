from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        strict=True,
    )

    database_url: str = "postgresql+asyncpg://hazlo:hazlo@localhost:5433/hazlo"
    hazlo_env: Literal["development", "production", "test"] = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()

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
    hazlo_env: Literal["dev", "development", "production", "test"] = "development"
    admin_user: str = "admin"
    admin_password: str = ""
    auto_approve_threshold: float = 0.95
    hazlo_secret_key: str = ""
    verify_ssl: bool = True
    ca_bundle: str | None = None
    ssl_cert_file: str | None = None
    llm_circuit_breaker_failure_threshold: int = 3
    llm_circuit_breaker_reset_timeout_seconds: float = 60.0
    prefect_server_analytics_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()

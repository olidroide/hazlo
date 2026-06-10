from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        strict=True,
        env_prefix="HAZLO_",
    )

    database_url: str = "postgresql+asyncpg://hazlo:hazlo@localhost:5433/hazlo"
    admin_user: str = "admin"
    admin_password: str = ""
    auto_approve_threshold: float = 0.95
    secret_key: str = ""
    verify_ssl: bool = True
    ca_bundle: str | None = None
    prefect_api_url: str = "http://localhost:4200/api"
    prefect_work_pool_name: str = "local-pool"
    prefect_ingest_flow_timeout_seconds: int = 1500
    prefect_fetch_source_task_timeout_seconds: int = 1200
    rss_max_results: int = 30
    auto_migrate: bool = True
    raw_storage_backend: str = "local"
    raw_local_path: Path = Path("./data/raw")
    unified_reparse: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Crawler settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    crawler_host: str = "0.0.0.0"
    crawler_port: int = 8003
    log_level: LogLevel = "INFO"
    environment: str = "local"
    enrichment_base_url: str = "http://localhost:8001"
    enrichment_timeout_sec: float = 10.0


@lru_cache
def get_settings() -> Settings:
    return Settings()

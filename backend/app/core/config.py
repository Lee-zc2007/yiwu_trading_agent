from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    app_name: str = "TradeGuard AI API"
    app_version: str = "1.0.0"
    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'tradeguard_dev.db').as_posix()}"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "dev-only-change-me"
    default_merchant_id: int = 1
    agent_mode: str = "mock"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = 8

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

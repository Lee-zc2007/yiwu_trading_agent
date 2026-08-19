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
    agent_mode: str = "llm"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4.1-mini"
    llm_timeout_seconds: float = 60
    llm_max_retries: int = 2
    # 知识库 Embedding 与对话 LLM 独立配置。默认本地哈希向量可离线路演；
    # 生产环境可切换到 OpenAI-compatible Embedding API。
    embedding_provider: str = "local-hash"
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 384
    knowledge_chunk_size: int = 500
    knowledge_chunk_overlap: int = 80
    knowledge_top_k: int = 5
    knowledge_min_similarity: float = 0.05
    cors_origins: str = "http://localhost:3000"
    max_upload_mb: int = 8

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

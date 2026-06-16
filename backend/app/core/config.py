from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://evalforge:evalforge@localhost:5432/evalforge"
    redis_url: str = "redis://localhost:6379/0"
    health_check_timeout_seconds: float = 2.0
    run_mode: str = "sync"
    llm_provider: str = "groq"
    llm_model: str = "llama-3.1-8b-instant"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    api_key: str | None = None
    groq_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_API_KEY", "EVALFORGE_GROQ_API_KEY"),
    )

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_prefix="EVALFORGE_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

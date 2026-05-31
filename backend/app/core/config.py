from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://evalforge:evalforge@localhost:5432/evalforge"
    redis_url: str = "redis://localhost:6379/0"
    health_check_timeout_seconds: float = 2.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EVALFORGE_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://evalforge:evalforge@127.0.0.1:5432/evalforge"
    redis_url: str = "redis://127.0.0.1:6379/0"
    health_check_timeout_seconds: float = 2.0
    run_mode: str = "sync"
    llm_provider: str = "groq"
    llm_model: str = "llama-3.1-8b-instant"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    api_key: str | None = None
    auth_token_pepper: str = "development-only-pepper"
    bootstrap_token: str | None = None
    session_ttl_hours: int = 12
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    allowed_hosts: str = "127.0.0.1,localhost,test,testserver"
    metrics_token: str | None = None
    otel_service_name: str = "evalforge-api"
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_headers: str | None = None
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1
    allowed_adapter_modules: str = (
        "app.adapters.demo_rag,app.adapters.groq_chat,app.adapters.llm_rag"
    )
    llm_allowed_hosts: str = "api.openai.com,api.groq.com"
    llm_api_key_env_allowlist: str = "OPENAI_API_KEY,GROQ_API_KEY"
    allow_private_provider_urls: bool = False
    groq_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GROQ_API_KEY", "EVALFORGE_GROQ_API_KEY"),
    )

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_prefix="EVALFORGE_",
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def normalize_database_driver(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @model_validator(mode="after")
    def require_auth_in_production(self) -> "Settings":
        if self.environment.lower() in {"production", "prod"}:
            if self.auth_token_pepper == "development-only-pepper":
                raise ValueError("EVALFORGE_AUTH_TOKEN_PEPPER must be set in production")
            if not self.bootstrap_token:
                raise ValueError("EVALFORGE_BOOTSTRAP_TOKEN must be set in production")
            if not self.metrics_token:
                raise ValueError("EVALFORGE_METRICS_TOKEN must be set in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

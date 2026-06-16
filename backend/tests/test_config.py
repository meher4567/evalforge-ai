from app.core.config import Settings


def test_settings_read_evalforge_environment_variables(monkeypatch):
    monkeypatch.setenv("EVALFORGE_ENVIRONMENT", "test")
    monkeypatch.setenv(
        "EVALFORGE_DATABASE_URL",
        "postgresql+asyncpg://user:pass@db:5432/example",
    )
    monkeypatch.setenv("EVALFORGE_REDIS_URL", "redis://redis:6379/1")

    settings = Settings()

    assert settings.environment == "test"
    assert settings.database_url == "postgresql+asyncpg://user:pass@db:5432/example"
    assert settings.redis_url == "redis://redis:6379/1"


def test_settings_read_groq_key_and_llm_defaults(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("EVALFORGE_LLM_PROVIDER", "groq")
    monkeypatch.setenv("EVALFORGE_LLM_MODEL", "llama-test-model")
    monkeypatch.setenv("EVALFORGE_LLM_BASE_URL", "https://example.test/openai/v1")

    settings = Settings()

    assert settings.groq_api_key == "test-groq-key"
    assert settings.llm_provider == "groq"
    assert settings.llm_model == "llama-test-model"
    assert settings.llm_base_url == "https://example.test/openai/v1"

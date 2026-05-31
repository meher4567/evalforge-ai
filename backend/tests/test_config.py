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

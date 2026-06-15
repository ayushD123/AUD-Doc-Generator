from app.core.config import Settings


def test_settings_use_local_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings()

    assert settings.APP_NAME == "aud-generator-api"
    assert settings.ENVIRONMENT == "local"
    assert settings.DATABASE_URL == "sqlite:///./aud_generator.db"


def test_settings_can_be_overridden_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "custom-aud-api")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

    settings = Settings()

    assert settings.APP_NAME == "custom-aud-api"
    assert settings.ENVIRONMENT == "test"
    assert settings.DATABASE_URL == "sqlite:///./test.db"

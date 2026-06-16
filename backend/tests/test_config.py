from app.core.config import Settings


def test_settings_use_local_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LOCAL_STORAGE_ROOT", raising=False)
    monkeypatch.delenv("MAX_SPREADSHEET_ROWS_PER_SHEET", raising=False)

    settings = Settings()

    assert settings.APP_NAME == "aud-generator-api"
    assert settings.ENVIRONMENT == "local"
    assert settings.DATABASE_URL == "sqlite:///./aud_generator.db"
    assert settings.LOCAL_STORAGE_ROOT == "storage"
    assert settings.MAX_SPREADSHEET_ROWS_PER_SHEET == 200


def test_settings_can_be_overridden_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "custom-aud-api")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", "./test_storage")
    monkeypatch.setenv("MAX_SPREADSHEET_ROWS_PER_SHEET", "25")

    settings = Settings()

    assert settings.APP_NAME == "custom-aud-api"
    assert settings.ENVIRONMENT == "test"
    assert settings.DATABASE_URL == "sqlite:///./test.db"
    assert settings.LOCAL_STORAGE_ROOT == "./test_storage"
    assert settings.MAX_SPREADSHEET_ROWS_PER_SHEET == 25

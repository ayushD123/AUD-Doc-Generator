from app.core.config import Settings


def test_settings_use_local_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LOCAL_STORAGE_ROOT", raising=False)
    monkeypatch.delenv("MAX_SPREADSHEET_ROWS_PER_SHEET", raising=False)

    settings = Settings(_env_file=None)

    assert settings.APP_NAME == "aud-generator-api"
    assert settings.ENVIRONMENT == "local"
    assert settings.DATABASE_URL == "sqlite:///./aud_generator.db"
    assert settings.LOCAL_STORAGE_ROOT == "storage"
    assert settings.JOB_QUEUE_BACKEND == "local"
    assert settings.OCI_SPEECH_OUTPUT_PREFIX == "projects/{project_id}/speech/"
    assert settings.OCI_SPEECH_MODEL_TYPE == "WHISPER_MEDIUM"
    assert settings.OCI_SPEECH_LANGUAGE_CODE == "en"
    assert settings.OCI_SPEECH_TIMEOUT_SECONDS == 1800
    assert settings.MAX_SPREADSHEET_ROWS_PER_SHEET == 200


def test_settings_can_be_overridden_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "custom-aud-api")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", "./test_storage")
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "oci")
    monkeypatch.setenv("OCI_SPEECH_OUTPUT_PREFIX", "speech/{project_id}/")
    monkeypatch.setenv("OCI_SPEECH_MODEL_TYPE", "ORACLE")
    monkeypatch.setenv("OCI_SPEECH_LANGUAGE_CODE", "en-US")
    monkeypatch.setenv("OCI_SPEECH_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("MAX_SPREADSHEET_ROWS_PER_SHEET", "25")

    settings = Settings(_env_file=None)

    assert settings.APP_NAME == "custom-aud-api"
    assert settings.ENVIRONMENT == "test"
    assert settings.DATABASE_URL == "sqlite:///./test.db"
    assert settings.LOCAL_STORAGE_ROOT == "./test_storage"
    assert settings.JOB_QUEUE_BACKEND == "oci"
    assert settings.OCI_SPEECH_OUTPUT_PREFIX == "speech/{project_id}/"
    assert settings.OCI_SPEECH_MODEL_TYPE == "ORACLE"
    assert settings.OCI_SPEECH_LANGUAGE_CODE == "en-US"
    assert settings.OCI_SPEECH_TIMEOUT_SECONDS == 5
    assert settings.MAX_SPREADSHEET_ROWS_PER_SHEET == 25

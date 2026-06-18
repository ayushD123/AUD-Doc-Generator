from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "aud-generator-api"
    ENVIRONMENT: str = "local"
    DATABASE_URL: str = "sqlite:///./aud_generator.db"
    STORAGE_BACKEND: str = "local"
    JOB_QUEUE_BACKEND: str = "local"
    LOCAL_STORAGE_ROOT: str = "storage"
    OCI_BUCKET_NAME: str | None = None
    OCI_NAMESPACE: str | None = None
    OCI_REGION: str | None = None
    OCI_COMPARTMENT_OCID: str | None = None
    OCI_CONFIG_FILE: str | None = None
    OCI_PROFILE: str | None = None
    OCI_QUEUE_OCID: str | None = None
    OCI_QUEUE_ENDPOINT: str | None = None
    OCI_SPEECH_COMPARTMENT_OCID: str | None = None
    OCI_SPEECH_OUTPUT_BUCKET: str | None = None
    OCI_SPEECH_OUTPUT_PREFIX: str = "projects/{project_id}/speech/"
    OCI_SPEECH_MODEL_TYPE: str = "WHISPER_MEDIUM"
    OCI_SPEECH_LANGUAGE_CODE: str = "en"
    OCI_SPEECH_TIMEOUT_SECONDS: int = 1800
    OCI_SPEECH_POLL_INTERVAL_SECONDS: float = 10.0
    MAX_SPREADSHEET_ROWS_PER_SHEET: int = 200
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

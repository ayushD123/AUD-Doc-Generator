from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "aud-generator-api"
    ENVIRONMENT: str = "local"
    DATABASE_URL: str = "sqlite:///./aud_generator.db"
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_ROOT: str = "storage"
    OCI_BUCKET_NAME: str | None = None
    OCI_NAMESPACE: str | None = None
    OCI_REGION: str | None = None
    OCI_COMPARTMENT_OCID: str | None = None
    OCI_CONFIG_FILE: str | None = None
    OCI_PROFILE: str | None = None
    MAX_SPREADSHEET_ROWS_PER_SHEET: int = 200
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

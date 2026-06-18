from functools import lru_cache

from pydantic import field_validator
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
    DOCUMENT_AI_PROVIDER: str = "none"
    OCI_DOCUMENT_COMPARTMENT_OCID: str | None = None
    OCI_DOCUMENT_OUTPUT_BUCKET: str | None = None
    OCI_DOCUMENT_OUTPUT_PREFIX: str = (
        "projects/{project_id}/document_understanding/output/"
    )
    OCI_DOCUMENT_REGION: str | None = None
    OCI_DOCUMENT_TIMEOUT_SECONDS: int = 900
    OCI_DOCUMENT_POLL_INTERVAL_SECONDS: float = 10.0
    OCI_DOCUMENT_ENABLE_DOCX: bool = False
    OCI_DOCUMENT_ENABLE_PPTX: bool = False
    OCI_DOCUMENT_ENABLE_XLSX: bool = False
    OCI_DOCUMENT_ENABLE_PDF: bool = True
    OCI_DOCUMENT_ENABLE_IMAGES: bool = True
    LLM_PROVIDER: str = "none"
    OCI_GENAI_REGION: str | None = None
    OCI_GENAI_PROJECT_OCID: str | None = None
    OCI_GENAI_MODEL_ID: str | None = None
    OCI_GENAI_API_KEY: str | None = None
    OCI_GENAI_COMPARTMENT_OCID: str | None = None
    OCI_GENAI_MAX_INPUT_CHARS: int = 200000
    OCI_GENAI_TIMEOUT_SECONDS: int = 120
    OCI_GENAI_TEMPERATURE: float = 1
    OCI_GENAI_MAX_OUTPUT_TOKENS: int = 16000
    SECTION_EVIDENCE_MAX_CHARS: int = 30000
    MAX_SPREADSHEET_ROWS_PER_SHEET: int = 200
    INTERNAL_DEBUG_OUTPUT: bool = False
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator(
        "OCI_DOCUMENT_ENABLE_DOCX",
        "OCI_DOCUMENT_ENABLE_PPTX",
        "OCI_DOCUMENT_ENABLE_XLSX",
        "OCI_DOCUMENT_ENABLE_PDF",
        "OCI_DOCUMENT_ENABLE_IMAGES",
        "INTERNAL_DEBUG_OUTPUT",
        mode="before",
    )
    @classmethod
    def normalize_bool_typos(cls, value):
        if isinstance(value, str) and value.strip().lower() == "fasle":
            return False

        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

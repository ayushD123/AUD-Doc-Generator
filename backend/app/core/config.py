from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "aud-generator-api"
    ENVIRONMENT: str = "local"
    DB_PROVIDER: str = "sqlite"
    DATABASE_URL: str | None = None
    AUTO_CREATE_TABLES: bool | None = None
    ORACLE_DB_USER: str | None = None
    ORACLE_DB_PASSWORD: str | None = None
    ORACLE_DB_DSN: str | None = None
    ORACLE_DB_WALLET_DIR: str | None = None
    ORACLE_DB_WALLET_PASSWORD: str | None = None
    ORACLE_DB_ECHO: bool = False
    ORACLE_DB_POOL_SIZE: int = 5
    ORACLE_DB_MAX_OVERFLOW: int = 10
    ORACLE_DB_POOL_PRE_PING: bool = True
    STORAGE_BACKEND: str = "local"
    JOB_QUEUE_BACKEND: str = "local"
    LOCAL_WORKER_POLL_INTERVAL_SECONDS: float = 5.0
    LOCAL_STORAGE_ROOT: str = "storage"
    OCI_BUCKET_NAME: str | None = None
    OCI_NAMESPACE: str | None = None
    OCI_REGION: str | None = None
    OCI_COMPARTMENT_OCID: str | None = None
    OCI_CONFIG_FILE: str | None = None
    OCI_PROFILE: str | None = None
    OCI_MULTIPART_UPLOAD_THRESHOLD_BYTES: int = 50 * 1024 * 1024
    OCI_MULTIPART_UPLOAD_PART_SIZE_BYTES: int = 10 * 1024 * 1024
    OCI_MULTIPART_UPLOAD_PARALLEL_WORKERS: int = 4
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
    OCI_GENAI_RETRY_MAX_ATTEMPTS: int = 4
    OCI_GENAI_RETRY_BASE_SECONDS: float = 2.0
    OCI_GENAI_RETRY_MAX_SECONDS: float = 20.0
    SECTION_EVIDENCE_MAX_CHARS: int = 30000
    REQUIRE_LLM_ENHANCED_OPEN_POINTS: bool = True
    ALLOW_RAW_OPEN_POINTS_FALLBACK: bool = True
    DEFAULT_AUD_TEMPLATE_PATH: str = "/backend/template/AUD_Editable_Template.docx"
    MAX_SPREADSHEET_ROWS_PER_SHEET: int = 200
    INTERNAL_DEBUG_OUTPUT: bool = False
    EMAIL_NOTIFICATIONS_ENABLED: bool = True
    EMAIL_NOTIFICATION_URL: str | None = (
        "https://apex.oraclecorp.com/pls/apex/basic_learning_01/apka/send-email"
    )
    EMAIL_NOTIFICATION_FROM: str = "audacle@oracle.com"
    EMAIL_NOTIFICATION_DOWNLOAD_BASE_URL: str | None = None
    EMAIL_NOTIFICATION_TIMEOUT_SECONDS: float = 10.0
    EMAIL_NOTIFICATION_VERIFY_SSL: bool = True
    EMAIL_NOTIFICATION_CA_BUNDLE: str | None = None
    EMAIL_NOTIFICATION_TRUST_ENV: bool = True
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
        "REQUIRE_LLM_ENHANCED_OPEN_POINTS",
        "ALLOW_RAW_OPEN_POINTS_FALLBACK",
        "ORACLE_DB_ECHO",
        "ORACLE_DB_POOL_PRE_PING",
        "AUTO_CREATE_TABLES",
        "EMAIL_NOTIFICATIONS_ENABLED",
        "EMAIL_NOTIFICATION_VERIFY_SSL",
        "EMAIL_NOTIFICATION_TRUST_ENV",
        mode="before",
    )
    @classmethod
    def normalize_bool_typos(cls, value):
        if isinstance(value, str) and value.strip().lower() == "fasle":
            return False

        return value

    def should_auto_create_tables(self) -> bool:
        if self.AUTO_CREATE_TABLES is not None:
            return self.AUTO_CREATE_TABLES

        return self.DB_PROVIDER.strip().lower() != "oracle"


@lru_cache
def get_settings() -> Settings:
    return Settings()

from app.core.config import Settings


def test_settings_use_local_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("DB_PROVIDER", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AUTO_CREATE_TABLES", raising=False)
    monkeypatch.delenv("ORACLE_DB_USER", raising=False)
    monkeypatch.delenv("ORACLE_DB_PASSWORD", raising=False)
    monkeypatch.delenv("ORACLE_DB_DSN", raising=False)
    monkeypatch.delenv("ORACLE_DB_WALLET_DIR", raising=False)
    monkeypatch.delenv("ORACLE_DB_WALLET_PASSWORD", raising=False)
    monkeypatch.delenv("ORACLE_DB_ECHO", raising=False)
    monkeypatch.delenv("ORACLE_DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("ORACLE_DB_MAX_OVERFLOW", raising=False)
    monkeypatch.delenv("ORACLE_DB_POOL_PRE_PING", raising=False)
    monkeypatch.delenv("LOCAL_STORAGE_ROOT", raising=False)
    monkeypatch.delenv("LOCAL_WORKER_POLL_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("MAX_SPREADSHEET_ROWS_PER_SHEET", raising=False)
    monkeypatch.delenv("DOCUMENT_AI_PROVIDER", raising=False)
    monkeypatch.delenv("OCI_DOCUMENT_OUTPUT_PREFIX", raising=False)
    monkeypatch.delenv("OCI_DOCUMENT_ENABLE_DOCX", raising=False)
    monkeypatch.delenv("OCI_DOCUMENT_ENABLE_PPTX", raising=False)
    monkeypatch.delenv("OCI_DOCUMENT_ENABLE_XLSX", raising=False)
    monkeypatch.delenv("OCI_DOCUMENT_ENABLE_PDF", raising=False)
    monkeypatch.delenv("OCI_DOCUMENT_ENABLE_IMAGES", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OCI_GENAI_REGION", raising=False)
    monkeypatch.delenv("OCI_GENAI_PROJECT_OCID", raising=False)
    monkeypatch.delenv("OCI_GENAI_MODEL_ID", raising=False)
    monkeypatch.delenv("OCI_GENAI_API_KEY", raising=False)
    monkeypatch.delenv("OCI_GENAI_COMPARTMENT_OCID", raising=False)
    monkeypatch.delenv("OCI_GENAI_MAX_INPUT_CHARS", raising=False)
    monkeypatch.delenv("OCI_GENAI_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("OCI_GENAI_TEMPERATURE", raising=False)
    monkeypatch.delenv("OCI_GENAI_MAX_OUTPUT_TOKENS", raising=False)
    monkeypatch.delenv("OCI_GENAI_RETRY_MAX_ATTEMPTS", raising=False)
    monkeypatch.delenv("OCI_GENAI_RETRY_BASE_SECONDS", raising=False)
    monkeypatch.delenv("OCI_GENAI_RETRY_MAX_SECONDS", raising=False)
    monkeypatch.delenv("SECTION_EVIDENCE_MAX_CHARS", raising=False)
    monkeypatch.delenv("REQUIRE_LLM_ENHANCED_OPEN_POINTS", raising=False)
    monkeypatch.delenv("ALLOW_RAW_OPEN_POINTS_FALLBACK", raising=False)
    monkeypatch.delenv("DEFAULT_AUD_TEMPLATE_PATH", raising=False)
    monkeypatch.delenv("EMAIL_NOTIFICATIONS_ENABLED", raising=False)
    monkeypatch.delenv("EMAIL_NOTIFICATION_URL", raising=False)
    monkeypatch.delenv("EMAIL_NOTIFICATION_FROM", raising=False)
    monkeypatch.delenv("EMAIL_NOTIFICATION_DOWNLOAD_BASE_URL", raising=False)
    monkeypatch.delenv("EMAIL_NOTIFICATION_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("EMAIL_NOTIFICATION_VERIFY_SSL", raising=False)
    monkeypatch.delenv("EMAIL_NOTIFICATION_CA_BUNDLE", raising=False)
    monkeypatch.delenv("EMAIL_NOTIFICATION_TRUST_ENV", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("OCI_GENAI_MAX_INPUT_CHARS", "200000")
    monkeypatch.setenv("OCI_GENAI_TIMEOUT_SECONDS", "120")
    monkeypatch.setenv("OCI_GENAI_TEMPERATURE", "1")
    monkeypatch.setenv("OCI_GENAI_MAX_OUTPUT_TOKENS", "16000")
    monkeypatch.setenv("SECTION_EVIDENCE_MAX_CHARS", "30000")

    settings = Settings(_env_file=None)

    assert settings.APP_NAME == "aud-generator-api"
    assert settings.ENVIRONMENT == "local"
    assert settings.DB_PROVIDER == "sqlite"
    assert settings.DATABASE_URL is None
    assert settings.AUTO_CREATE_TABLES is None
    assert settings.should_auto_create_tables() is True
    assert settings.ORACLE_DB_USER is None
    assert settings.ORACLE_DB_PASSWORD is None
    assert settings.ORACLE_DB_DSN is None
    assert settings.ORACLE_DB_WALLET_DIR is None
    assert settings.ORACLE_DB_WALLET_PASSWORD is None
    assert settings.ORACLE_DB_ECHO is False
    assert settings.ORACLE_DB_POOL_SIZE == 5
    assert settings.ORACLE_DB_MAX_OVERFLOW == 10
    assert settings.ORACLE_DB_POOL_PRE_PING is True
    assert settings.LOCAL_STORAGE_ROOT == "storage"
    assert settings.JOB_QUEUE_BACKEND == "local"
    assert settings.LOCAL_WORKER_POLL_INTERVAL_SECONDS == 5.0
    assert settings.OCI_SPEECH_OUTPUT_PREFIX == "projects/{project_id}/speech/"
    assert settings.OCI_SPEECH_MODEL_TYPE == "WHISPER_MEDIUM"
    assert settings.OCI_SPEECH_LANGUAGE_CODE == "en"
    assert settings.OCI_SPEECH_TIMEOUT_SECONDS == 1800
    assert settings.DOCUMENT_AI_PROVIDER == "none"
    assert settings.OCI_DOCUMENT_OUTPUT_PREFIX == (
        "projects/{project_id}/document_understanding/output/"
    )
    assert settings.OCI_DOCUMENT_ENABLE_PDF is True
    assert settings.OCI_DOCUMENT_ENABLE_XLSX is False
    assert settings.LLM_PROVIDER == "none"
    assert settings.OCI_GENAI_MAX_INPUT_CHARS == 200000
    assert settings.OCI_GENAI_TIMEOUT_SECONDS == 120
    assert settings.OCI_GENAI_TEMPERATURE == 1
    assert settings.OCI_GENAI_MAX_OUTPUT_TOKENS == 16000
    assert settings.OCI_GENAI_RETRY_MAX_ATTEMPTS == 4
    assert settings.OCI_GENAI_RETRY_BASE_SECONDS == 2.0
    assert settings.OCI_GENAI_RETRY_MAX_SECONDS == 20.0
    assert settings.SECTION_EVIDENCE_MAX_CHARS == 30000
    assert settings.REQUIRE_LLM_ENHANCED_OPEN_POINTS is True
    assert settings.ALLOW_RAW_OPEN_POINTS_FALLBACK is True
    assert settings.DEFAULT_AUD_TEMPLATE_PATH == (
        "/backend/template/AUD_Editable_Template.docx"
    )
    assert settings.MAX_SPREADSHEET_ROWS_PER_SHEET == 200
    assert settings.EMAIL_NOTIFICATIONS_ENABLED is True
    assert settings.EMAIL_NOTIFICATION_URL == (
        "https://apex.oraclecorp.com/pls/apex/basic_learning_01/apka/send-email"
    )
    assert settings.EMAIL_NOTIFICATION_FROM == "audacle@oracle.com"
    assert settings.EMAIL_NOTIFICATION_DOWNLOAD_BASE_URL is None
    assert settings.EMAIL_NOTIFICATION_TIMEOUT_SECONDS == 10.0
    assert settings.EMAIL_NOTIFICATION_VERIFY_SSL is True
    assert settings.EMAIL_NOTIFICATION_CA_BUNDLE is None
    assert settings.EMAIL_NOTIFICATION_TRUST_ENV is True


def test_settings_can_be_overridden_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "custom-aud-api")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DB_PROVIDER", "oracle")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("AUTO_CREATE_TABLES", "false")
    monkeypatch.setenv("ORACLE_DB_USER", "aud_user")
    monkeypatch.setenv("ORACLE_DB_PASSWORD", "secret")
    monkeypatch.setenv("ORACLE_DB_DSN", "adb_high")
    monkeypatch.setenv("ORACLE_DB_WALLET_DIR", "C:/wallets/aud")
    monkeypatch.setenv("ORACLE_DB_WALLET_PASSWORD", "wallet-secret")
    monkeypatch.setenv("ORACLE_DB_ECHO", "true")
    monkeypatch.setenv("ORACLE_DB_POOL_SIZE", "9")
    monkeypatch.setenv("ORACLE_DB_MAX_OVERFLOW", "4")
    monkeypatch.setenv("ORACLE_DB_POOL_PRE_PING", "false")
    monkeypatch.setenv("LOCAL_STORAGE_ROOT", "./test_storage")
    monkeypatch.setenv("JOB_QUEUE_BACKEND", "oci")
    monkeypatch.setenv("LOCAL_WORKER_POLL_INTERVAL_SECONDS", "1.5")
    monkeypatch.setenv("OCI_SPEECH_OUTPUT_PREFIX", "speech/{project_id}/")
    monkeypatch.setenv("OCI_SPEECH_MODEL_TYPE", "ORACLE")
    monkeypatch.setenv("OCI_SPEECH_LANGUAGE_CODE", "en-US")
    monkeypatch.setenv("OCI_SPEECH_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("DOCUMENT_AI_PROVIDER", "oci_document_understanding")
    monkeypatch.setenv("OCI_DOCUMENT_OUTPUT_PREFIX", "du/{project_id}/")
    monkeypatch.setenv("OCI_DOCUMENT_ENABLE_PDF", "false")
    monkeypatch.setenv("OCI_DOCUMENT_ENABLE_XLSX", "true")
    monkeypatch.setenv("LLM_PROVIDER", "oci_responses")
    monkeypatch.setenv("OCI_GENAI_REGION", "us-chicago-1")
    monkeypatch.setenv("OCI_GENAI_PROJECT_OCID", "ocid1.genaiagentproject.oc1..test")
    monkeypatch.setenv("OCI_GENAI_MODEL_ID", "ocid1.generativeaimodel.oc1..test")
    monkeypatch.setenv("OCI_GENAI_API_KEY", "dev-key")
    monkeypatch.setenv("OCI_GENAI_COMPARTMENT_OCID", "ocid1.compartment.oc1..test")
    monkeypatch.setenv("OCI_GENAI_MAX_INPUT_CHARS", "12000")
    monkeypatch.setenv("OCI_GENAI_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("OCI_GENAI_TEMPERATURE", "0.2")
    monkeypatch.setenv("OCI_GENAI_MAX_OUTPUT_TOKENS", "1500")
    monkeypatch.setenv("OCI_GENAI_RETRY_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("OCI_GENAI_RETRY_BASE_SECONDS", "0.5")
    monkeypatch.setenv("OCI_GENAI_RETRY_MAX_SECONDS", "6")
    monkeypatch.setenv("SECTION_EVIDENCE_MAX_CHARS", "5000")
    monkeypatch.setenv("REQUIRE_LLM_ENHANCED_OPEN_POINTS", "false")
    monkeypatch.setenv("ALLOW_RAW_OPEN_POINTS_FALLBACK", "false")
    monkeypatch.setenv("DEFAULT_AUD_TEMPLATE_PATH", "/custom/template.docx")
    monkeypatch.setenv("MAX_SPREADSHEET_ROWS_PER_SHEET", "25")
    monkeypatch.setenv("EMAIL_NOTIFICATIONS_ENABLED", "false")
    monkeypatch.setenv("EMAIL_NOTIFICATION_URL", "https://example.test/email")
    monkeypatch.setenv("EMAIL_NOTIFICATION_FROM", "custom@oracle.com")
    monkeypatch.setenv(
        "EMAIL_NOTIFICATION_DOWNLOAD_BASE_URL",
        "https://aud.example.com/api",
    )
    monkeypatch.setenv("EMAIL_NOTIFICATION_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("EMAIL_NOTIFICATION_VERIFY_SSL", "false")
    monkeypatch.setenv("EMAIL_NOTIFICATION_CA_BUNDLE", "C:/certs/oracle-ca.pem")
    monkeypatch.setenv("EMAIL_NOTIFICATION_TRUST_ENV", "false")

    settings = Settings(_env_file=None)

    assert settings.APP_NAME == "custom-aud-api"
    assert settings.ENVIRONMENT == "test"
    assert settings.DB_PROVIDER == "oracle"
    assert settings.DATABASE_URL == "sqlite:///./test.db"
    assert settings.AUTO_CREATE_TABLES is False
    assert settings.should_auto_create_tables() is False
    assert settings.ORACLE_DB_USER == "aud_user"
    assert settings.ORACLE_DB_PASSWORD == "secret"
    assert settings.ORACLE_DB_DSN == "adb_high"
    assert settings.ORACLE_DB_WALLET_DIR == "C:/wallets/aud"
    assert settings.ORACLE_DB_WALLET_PASSWORD == "wallet-secret"
    assert settings.ORACLE_DB_ECHO is True
    assert settings.ORACLE_DB_POOL_SIZE == 9
    assert settings.ORACLE_DB_MAX_OVERFLOW == 4
    assert settings.ORACLE_DB_POOL_PRE_PING is False
    assert settings.LOCAL_STORAGE_ROOT == "./test_storage"
    assert settings.JOB_QUEUE_BACKEND == "oci"
    assert settings.LOCAL_WORKER_POLL_INTERVAL_SECONDS == 1.5
    assert settings.OCI_SPEECH_OUTPUT_PREFIX == "speech/{project_id}/"
    assert settings.OCI_SPEECH_MODEL_TYPE == "ORACLE"
    assert settings.OCI_SPEECH_LANGUAGE_CODE == "en-US"
    assert settings.OCI_SPEECH_TIMEOUT_SECONDS == 5
    assert settings.DOCUMENT_AI_PROVIDER == "oci_document_understanding"
    assert settings.OCI_DOCUMENT_OUTPUT_PREFIX == "du/{project_id}/"
    assert settings.OCI_DOCUMENT_ENABLE_PDF is False
    assert settings.OCI_DOCUMENT_ENABLE_XLSX is True
    assert settings.LLM_PROVIDER == "oci_responses"
    assert settings.OCI_GENAI_REGION == "us-chicago-1"
    assert settings.OCI_GENAI_PROJECT_OCID == "ocid1.genaiagentproject.oc1..test"
    assert settings.OCI_GENAI_MODEL_ID == "ocid1.generativeaimodel.oc1..test"
    assert settings.OCI_GENAI_API_KEY == "dev-key"
    assert settings.OCI_GENAI_COMPARTMENT_OCID == "ocid1.compartment.oc1..test"
    assert settings.OCI_GENAI_MAX_INPUT_CHARS == 12000
    assert settings.OCI_GENAI_TIMEOUT_SECONDS == 30
    assert settings.OCI_GENAI_TEMPERATURE == 0.2
    assert settings.OCI_GENAI_MAX_OUTPUT_TOKENS == 1500
    assert settings.OCI_GENAI_RETRY_MAX_ATTEMPTS == 5
    assert settings.OCI_GENAI_RETRY_BASE_SECONDS == 0.5
    assert settings.OCI_GENAI_RETRY_MAX_SECONDS == 6
    assert settings.SECTION_EVIDENCE_MAX_CHARS == 5000
    assert settings.REQUIRE_LLM_ENHANCED_OPEN_POINTS is False
    assert settings.ALLOW_RAW_OPEN_POINTS_FALLBACK is False
    assert settings.DEFAULT_AUD_TEMPLATE_PATH == "/custom/template.docx"
    assert settings.MAX_SPREADSHEET_ROWS_PER_SHEET == 25
    assert settings.EMAIL_NOTIFICATIONS_ENABLED is False
    assert settings.EMAIL_NOTIFICATION_URL == "https://example.test/email"
    assert settings.EMAIL_NOTIFICATION_FROM == "custom@oracle.com"
    assert settings.EMAIL_NOTIFICATION_DOWNLOAD_BASE_URL == (
        "https://aud.example.com/api"
    )
    assert settings.EMAIL_NOTIFICATION_TIMEOUT_SECONDS == 2.5
    assert settings.EMAIL_NOTIFICATION_VERIFY_SSL is False
    assert settings.EMAIL_NOTIFICATION_CA_BUNDLE == "C:/certs/oracle-ca.pem"
    assert settings.EMAIL_NOTIFICATION_TRUST_ENV is False


def test_settings_accept_common_false_typo_for_document_flags(monkeypatch) -> None:
    monkeypatch.setenv("OCI_DOCUMENT_ENABLE_DOCX", "fasle")

    settings = Settings(_env_file=None)

    assert settings.OCI_DOCUMENT_ENABLE_DOCX is False


def test_auto_create_tables_defaults_false_for_oracle(monkeypatch) -> None:
    monkeypatch.delenv("AUTO_CREATE_TABLES", raising=False)

    settings = Settings(DB_PROVIDER="oracle", _env_file=None)

    assert settings.AUTO_CREATE_TABLES is None
    assert settings.should_auto_create_tables() is False

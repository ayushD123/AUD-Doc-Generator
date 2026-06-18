from app.core.config import Settings


def test_settings_use_local_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LOCAL_STORAGE_ROOT", raising=False)
    monkeypatch.delenv("MAX_SPREADSHEET_ROWS_PER_SHEET", raising=False)
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
    monkeypatch.delenv("SECTION_EVIDENCE_MAX_CHARS", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("OCI_GENAI_MAX_INPUT_CHARS", "200000")
    monkeypatch.setenv("OCI_GENAI_TIMEOUT_SECONDS", "120")
    monkeypatch.setenv("OCI_GENAI_TEMPERATURE", "1")
    monkeypatch.setenv("OCI_GENAI_MAX_OUTPUT_TOKENS", "16000")
    monkeypatch.setenv("SECTION_EVIDENCE_MAX_CHARS", "30000")

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
    assert settings.SECTION_EVIDENCE_MAX_CHARS == 30000
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
    monkeypatch.setenv("SECTION_EVIDENCE_MAX_CHARS", "5000")
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
    assert settings.SECTION_EVIDENCE_MAX_CHARS == 5000
    assert settings.MAX_SPREADSHEET_ROWS_PER_SHEET == 25


def test_settings_accept_common_false_typo_for_document_flags(monkeypatch) -> None:
    monkeypatch.setenv("OCI_DOCUMENT_ENABLE_DOCX", "fasle")

    settings = Settings(_env_file=None)

    assert settings.OCI_DOCUMENT_ENABLE_DOCX is False

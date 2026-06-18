from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from typing import Any, Protocol

from app.core.config import Settings, get_settings
from app.models import UploadedFile


DOCUMENT_UNDERSTANDING_CONTENT_TYPE = "oci_document_understanding"
TERMINAL_PROCESSOR_STATES = {"SUCCEEDED", "FAILED", "CANCELED", "CANCELLED"}
DOCUMENT_DISPLAY_NAME_MAX_LENGTH = 255
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


class DocumentIntelligenceService(Protocol):
    provider_name: str

    def analyze_document(
        self,
        project_id: str,
        uploaded_file: UploadedFile,
        job_id: str,
    ) -> dict[str, Any] | None:
        ...


class NoOpDocumentIntelligenceService:
    provider_name = "none"

    def analyze_document(
        self,
        project_id: str,
        uploaded_file: UploadedFile,
        job_id: str,
    ) -> dict[str, Any] | None:
        return None


@dataclass
class NormalizedDocumentUnderstandingResult:
    provider: str
    processor_job_id: str
    document_metadata: dict[str, Any]
    pages: list[dict[str, Any]]
    detected_document_types: list[dict[str, Any]]
    tables: list[dict[str, Any]]
    raw_result_object_path: str
    source_uploaded_file_id: str
    text: str

    def as_json_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "processor_job_id": self.processor_job_id,
            "document_metadata": self.document_metadata,
            "pages": self.pages,
            "detected_document_types": self.detected_document_types,
            "tables": self.tables,
            "raw_result_object_path": self.raw_result_object_path,
            "source_uploaded_file_id": self.source_uploaded_file_id,
        }


def build_document_display_name(uploaded_file: UploadedFile) -> str:
    filename_stem = Path(uploaded_file.original_filename or "document").stem
    raw_name = f"AUD_document_{filename_stem}_{uploaded_file.id}"
    safe_name = "".join(
        character
        if character.isascii() and (character.isalnum() or character in {"-", "_"})
        else "_"
        for character in raw_name
    )
    safe_name = re.sub(r"_+", "_", safe_name).strip("_-")
    return (safe_name or f"AUD_document_{uploaded_file.id}")[
        :DOCUMENT_DISPLAY_NAME_MAX_LENGTH
    ]


def format_document_output_prefix(
    template: str,
    project_id: str,
    job_id: str,
    uploaded_file_id: str,
) -> str:
    try:
        base_prefix = template.format(project_id=project_id)
    except KeyError as error:
        raise ValueError(
            "OCI_DOCUMENT_OUTPUT_PREFIX may only use the {project_id} placeholder."
        ) from error

    normalized_prefix = base_prefix.strip("/")
    if normalized_prefix:
        normalized_prefix = f"{normalized_prefix}/"

    return f"{normalized_prefix}{job_id}/{uploaded_file_id}/"


def get_file_extension(uploaded_file: UploadedFile) -> str:
    return Path(uploaded_file.original_filename or "").suffix.lower()


def is_document_understanding_eligible(
    uploaded_file: UploadedFile,
    settings: Settings,
) -> bool:
    extension = get_file_extension(uploaded_file)

    if extension == ".pdf":
        return settings.OCI_DOCUMENT_ENABLE_PDF
    if extension == ".docx":
        return settings.OCI_DOCUMENT_ENABLE_DOCX
    if extension == ".pptx":
        return settings.OCI_DOCUMENT_ENABLE_PPTX
    if extension in {".xlsx", ".xlsm"}:
        return settings.OCI_DOCUMENT_ENABLE_XLSX
    if extension in IMAGE_EXTENSIONS:
        return settings.OCI_DOCUMENT_ENABLE_IMAGES

    return False


def compact_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def normalize_page_text(page: dict[str, Any]) -> str:
    lines = page.get("lines") or page.get("detectedLines") or []
    line_text = [
        compact_text(line.get("text") or line.get("value"))
        for line in lines
        if isinstance(line, dict)
    ]
    line_text = [text for text in line_text if text]
    if line_text:
        return "\n".join(line_text)

    words = page.get("words") or page.get("detectedWords") or []
    word_text = [
        compact_text(word.get("text") or word.get("value"))
        for word in words
        if isinstance(word, dict)
    ]
    return " ".join(text for text in word_text if text)


def normalize_table(table: dict[str, Any], table_index: int, page_number: Any) -> dict[str, Any]:
    rows: dict[int, dict[int, str]] = {}
    cells = table.get("bodyRows") or table.get("cells") or []

    for row_index, row in enumerate(cells):
        if isinstance(row, list):
            for column_index, cell in enumerate(row):
                cell_text = (
                    compact_text(cell.get("text") or cell.get("value"))
                    if isinstance(cell, dict)
                    else compact_text(cell)
                )
                rows.setdefault(row_index, {})[column_index] = cell_text
        elif isinstance(row, dict):
            row_number = int(row.get("rowIndex") or row.get("row_index") or row_index)
            column_number = int(row.get("columnIndex") or row.get("column_index") or 0)
            cell_text = compact_text(row.get("text") or row.get("value"))
            rows.setdefault(row_number, {})[column_number] = cell_text

    normalized_rows = [
        [columns[column_index] for column_index in sorted(columns)]
        for row_number, columns in sorted(rows.items())
    ]

    return {
        "index": table_index,
        "page_number": page_number,
        "rows": normalized_rows,
    }


def normalize_document_understanding_result(
    raw_result: dict[str, Any],
    processor_job_id: str,
    raw_result_object_path: str,
    uploaded_file: UploadedFile,
) -> NormalizedDocumentUnderstandingResult:
    pages = raw_result.get("pages") or raw_result.get("documentPages") or []
    normalized_pages: list[dict[str, Any]] = []
    normalized_tables: list[dict[str, Any]] = []
    text_blocks: list[str] = []

    for page_index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue

        page_number = page.get("pageNumber") or page.get("page_number") or page_index
        page_text = normalize_page_text(page)
        if page_text:
            text_blocks.append(f"Page {page_number}\n{page_text}")

        page_tables = page.get("tables") or []
        for table in page_tables:
            if isinstance(table, dict):
                normalized_tables.append(
                    normalize_table(table, len(normalized_tables) + 1, page_number)
                )

        normalized_pages.append(
            {
                "page_number": page_number,
                "text": page_text,
                "table_count": len(page_tables),
            }
        )

    detected_document_types = (
        raw_result.get("detectedDocumentTypes")
        or raw_result.get("detected_document_types")
        or raw_result.get("documentTypes")
        or []
    )

    return NormalizedDocumentUnderstandingResult(
        provider="oci_document_understanding",
        processor_job_id=processor_job_id,
        document_metadata=raw_result.get("documentMetadata") or {},
        pages=normalized_pages,
        detected_document_types=detected_document_types,
        tables=normalized_tables,
        raw_result_object_path=raw_result_object_path,
        source_uploaded_file_id=uploaded_file.id,
        text="\n\n".join(text_blocks).strip(),
    )


class OCIDocumentUnderstandingService:
    provider_name = "oci_document_understanding"

    def __init__(
        self,
        settings: Settings | None = None,
        document_client: object | None = None,
        object_storage_client: object | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.namespace = self.require_setting(
            self.settings.OCI_NAMESPACE,
            "OCI_NAMESPACE",
        )
        self.input_bucket = self.require_setting(
            self.settings.OCI_BUCKET_NAME,
            "OCI_BUCKET_NAME",
        )
        self.compartment_id = self.require_setting(
            self.settings.OCI_DOCUMENT_COMPARTMENT_OCID,
            "OCI_DOCUMENT_COMPARTMENT_OCID",
        )
        self.output_bucket = self.require_setting(
            self.settings.OCI_DOCUMENT_OUTPUT_BUCKET,
            "OCI_DOCUMENT_OUTPUT_BUCKET",
        )
        self.document_client = document_client or self.build_document_client()
        self.object_storage_client = (
            object_storage_client or self.build_object_storage_client()
        )

    @staticmethod
    def require_setting(value: str | None, setting_name: str) -> str:
        if not value:
            raise ValueError(
                f"{setting_name} is required for OCI Document Understanding."
            )

        return value

    def build_oci_config(self) -> dict[str, Any]:
        try:
            import oci
        except ImportError as error:
            raise RuntimeError(
                "OCI Python SDK is required for OCI Document Understanding."
            ) from error

        config_file = self.settings.OCI_CONFIG_FILE
        profile = self.settings.OCI_PROFILE or "DEFAULT"
        config = (
            oci.config.from_file(file_location=config_file, profile_name=profile)
            if config_file
            else oci.config.from_file(profile_name=profile)
        )
        region = self.settings.OCI_DOCUMENT_REGION or self.settings.OCI_REGION
        if region:
            config["region"] = region

        return config

    def build_document_client(self) -> object:
        try:
            import oci
        except ImportError as error:
            raise RuntimeError(
                "OCI Python SDK is required for OCI Document Understanding."
            ) from error

        return oci.ai_document.AIServiceDocumentClient(self.build_oci_config())

    def build_object_storage_client(self) -> object:
        try:
            import oci
        except ImportError as error:
            raise RuntimeError(
                "OCI Python SDK is required for OCI Document Understanding."
            ) from error

        return oci.object_storage.ObjectStorageClient(self.build_oci_config())

    def ensure_input_object_exists(self, object_name: str) -> None:
        self.object_storage_client.head_object(
            self.namespace,
            self.input_bucket,
            object_name,
        )

    def build_processor_features(self) -> list[object]:
        try:
            import oci
        except ImportError as error:
            raise RuntimeError(
                "OCI Python SDK is required for OCI Document Understanding."
            ) from error

        models = oci.ai_document.models
        return [
            models.DocumentTextExtractionFeature(
                feature_type=(
                    models.DocumentTextExtractionFeature.FEATURE_TYPE_TEXT_EXTRACTION
                )
            ),
            models.DocumentTableExtractionFeature(
                feature_type=(
                    models.DocumentTableExtractionFeature.FEATURE_TYPE_TABLE_EXTRACTION
                )
            ),
            models.DocumentClassificationFeature(
                feature_type=(
                    models.DocumentClassificationFeature
                    .FEATURE_TYPE_DOCUMENT_CLASSIFICATION
                ),
                max_results=5,
            ),
        ]

    def submit_processor_job(
        self,
        uploaded_file: UploadedFile,
        output_prefix: str,
    ) -> str:
        try:
            import oci
        except ImportError as error:
            raise RuntimeError(
                "OCI Python SDK is required for OCI Document Understanding."
            ) from error

        self.ensure_input_object_exists(uploaded_file.storage_path)
        models = oci.ai_document.models
        request = models.CreateProcessorJobDetails(
            display_name=build_document_display_name(uploaded_file),
            compartment_id=self.compartment_id,
            input_location=models.ObjectStorageLocations(
                source_type=(
                    models.ObjectStorageLocations
                    .SOURCE_TYPE_OBJECT_STORAGE_LOCATIONS
                ),
                object_locations=[
                    models.ObjectLocation(
                        namespace_name=self.namespace,
                        bucket_name=self.input_bucket,
                        object_name=uploaded_file.storage_path,
                    )
                ],
            ),
            output_location=models.OutputLocation(
                namespace_name=self.namespace,
                bucket_name=self.output_bucket,
                prefix=output_prefix,
            ),
            processor_config=models.GeneralProcessorConfig(
                processor_type=models.GeneralProcessorConfig.PROCESSOR_TYPE_GENERAL,
                document_type=models.GeneralProcessorConfig.DOCUMENT_TYPE_OTHERS,
                features=self.build_processor_features(),
            ),
        )
        response = self.document_client.create_processor_job(request)
        processor_job_id = getattr(response.data, "id", None)
        if not processor_job_id:
            raise RuntimeError(
                "OCI Document Understanding did not return a processor job OCID."
            )

        return processor_job_id

    def wait_for_completion(
        self,
        processor_job_id: str,
        timeout_seconds: int,
        poll_interval_seconds: float,
    ) -> str:
        deadline = monotonic() + timeout_seconds

        while True:
            response = self.document_client.get_processor_job(processor_job_id)
            status = str(getattr(response.data, "lifecycle_state", "")).upper()

            if status in TERMINAL_PROCESSOR_STATES:
                return status

            if monotonic() >= deadline:
                raise TimeoutError(
                    "OCI Document Understanding processor job "
                    f"{processor_job_id} timed out."
                )

            sleep(max(poll_interval_seconds, 0.1))

    def list_output_json_objects(self, output_prefix: str) -> list[str]:
        response = self.object_storage_client.list_objects(
            self.namespace,
            self.output_bucket,
            prefix=output_prefix,
        )
        objects = getattr(response.data, "objects", [])
        object_names = [getattr(item, "name", "") for item in objects]
        return sorted(
            object_name
            for object_name in object_names
            if object_name.lower().endswith(".json")
        )

    def read_json_object(self, object_name: str) -> dict[str, Any]:
        response = self.object_storage_client.get_object(
            self.namespace,
            self.output_bucket,
            object_name,
        )
        content = response.data.content
        if isinstance(content, bytes):
            content = content.decode("utf-8")

        return json.loads(content)

    def read_processor_output(
        self,
        processor_job_id: str,
        output_prefix: str,
        uploaded_file: UploadedFile,
    ) -> dict[str, Any]:
        output_object_names = self.list_output_json_objects(output_prefix)
        if not output_object_names:
            raise FileNotFoundError(
                "No OCI Document Understanding JSON output found under "
                f"{output_prefix}."
            )

        raw_result_object_path = output_object_names[0]
        raw_result = self.read_json_object(raw_result_object_path)
        normalized = normalize_document_understanding_result(
            raw_result=raw_result,
            processor_job_id=processor_job_id,
            raw_result_object_path=raw_result_object_path,
            uploaded_file=uploaded_file,
        )
        payload = normalized.as_json_payload()
        payload["text"] = normalized.text
        return payload

    def analyze_document(
        self,
        project_id: str,
        uploaded_file: UploadedFile,
        job_id: str,
    ) -> dict[str, Any] | None:
        if self.settings.STORAGE_BACKEND.strip().lower() != "oci":
            raise ValueError(
                "OCI Document Understanding requires STORAGE_BACKEND=oci because "
                "input documents must be available in Object Storage."
            )

        output_prefix = format_document_output_prefix(
            self.settings.OCI_DOCUMENT_OUTPUT_PREFIX,
            project_id,
            job_id,
            uploaded_file.id,
        )
        processor_job_id = self.submit_processor_job(uploaded_file, output_prefix)
        status = self.wait_for_completion(
            processor_job_id,
            timeout_seconds=self.settings.OCI_DOCUMENT_TIMEOUT_SECONDS,
            poll_interval_seconds=self.settings.OCI_DOCUMENT_POLL_INTERVAL_SECONDS,
        )
        if status != "SUCCEEDED":
            raise RuntimeError(
                "OCI Document Understanding processor job "
                f"{processor_job_id} ended with status {status}."
            )

        return self.read_processor_output(
            processor_job_id=processor_job_id,
            output_prefix=output_prefix,
            uploaded_file=uploaded_file,
        )


def get_document_intelligence_service() -> DocumentIntelligenceService:
    settings = get_settings()
    provider = settings.DOCUMENT_AI_PROVIDER.strip().lower()

    if provider == "none":
        return NoOpDocumentIntelligenceService()

    if provider == "oci_document_understanding":
        return OCIDocumentUnderstandingService(settings)

    raise ValueError(
        "DOCUMENT_AI_PROVIDER must be either 'none' or "
        "'oci_document_understanding'."
    )

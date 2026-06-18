import json
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep
from traceback import format_exception_only

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal, create_db_and_tables
from app.models import ExtractedContent, Job, UploadedFile
from app.services.file_storage import (
    LocalStorageService,
    StorageService,
    get_file_storage,
)

FILE_TYPE_BY_EXTENSION = {
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "spreadsheet",
    ".xlsm": "spreadsheet",
    ".txt": "transcript_text",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".tif": "image",
    ".tiff": "image",
    ".mp3": "media",
    ".m4a": "media",
    ".mp4": "media",
    ".pdf": "pdf",
}


@dataclass
class ExtractionResult:
    attempted_count: int = 0
    success_count: int = 0
    errors: list[str] = field(default_factory=list)

    def record_success(self) -> None:
        self.attempted_count += 1
        self.success_count += 1

    def record_error(self, uploaded_file: UploadedFile, error: Exception) -> None:
        self.attempted_count += 1
        error_detail = "".join(format_exception_only(type(error), error)).strip()
        self.errors.append(f"{uploaded_file.original_filename}: {error_detail}")


def classify_file_type(filename: str) -> str | None:
    return FILE_TYPE_BY_EXTENSION.get(Path(filename).suffix.lower())


def list_project_uploaded_files(session: Session, project_id: str) -> list[UploadedFile]:
    return list(
        session.scalars(
            select(UploadedFile).where(UploadedFile.project_id == project_id)
        ).all()
    )


def raise_or_record_extraction_error(
    result: ExtractionResult,
    uploaded_file: UploadedFile,
    error: Exception,
    continue_on_error: bool,
) -> None:
    if not continue_on_error:
        raise error

    result.record_error(uploaded_file, error)


def resolve_storage_service(
    storage_root: Path | None = None,
    storage_service: StorageService | None = None,
) -> StorageService:
    if storage_service is not None:
        return storage_service

    if storage_root is not None:
        return LocalStorageService(storage_root)

    return get_file_storage()


def materialize_storage_file(
    storage_service: StorageService,
    storage_key: str,
    work_dir: Path,
    filename: str,
) -> Path:
    local_path = storage_service.local_path(storage_key)
    if local_path is not None:
        return local_path

    destination = work_dir / filename
    storage_service.download_to_path(storage_key, destination)
    return destination


def process_classify_files_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
) -> None:
    job.status = "running"
    job.progress = 10
    job.message = "Classifying uploaded files."
    session.commit()

    sleep(sleep_seconds)

    uploaded_files = session.scalars(
        select(UploadedFile).where(UploadedFile.project_id == job.project_id)
    ).all()

    for uploaded_file in uploaded_files:
        uploaded_file.file_type = classify_file_type(uploaded_file.original_filename)

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Classified {len(uploaded_files)} uploaded file(s)."
    session.commit()


def should_extract_transcript(uploaded_file: UploadedFile) -> bool:
    extension = Path(uploaded_file.original_filename).suffix.lower()
    return uploaded_file.file_type == "transcript_text" or extension == ".txt"


def read_uploaded_text_file(
    storage_service: StorageService,
    uploaded_file: UploadedFile,
) -> str:
    return storage_service.read_bytes(uploaded_file.storage_path).decode(
        "utf-8",
        errors="replace",
    )


def extract_transcripts_for_project(
    session: Session,
    project_id: str,
    uploaded_files: list[UploadedFile],
    storage_service: StorageService,
    continue_on_error: bool = False,
) -> ExtractionResult:
    result = ExtractionResult()
    transcript_files = [
        uploaded_file
        for uploaded_file in uploaded_files
        if should_extract_transcript(uploaded_file)
    ]

    for uploaded_file in transcript_files:
        try:
            text_content = read_uploaded_text_file(storage_service, uploaded_file)
            extracted_content = ExtractedContent(
                project_id=project_id,
                uploaded_file_id=uploaded_file.id,
                content_type="transcript",
                title=uploaded_file.original_filename,
                text_content=text_content,
                json_content=json.dumps(
                    {
                        "character_count": len(text_content),
                        "word_count": len(text_content.split()),
                    }
                ),
            )
            session.add(extracted_content)
            result.record_success()
        except Exception as error:
            raise_or_record_extraction_error(
                result,
                uploaded_file,
                error,
                continue_on_error,
            )

    return result


def process_extract_transcripts_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
    storage_root: Path | None = None,
) -> None:
    job.status = "running"
    job.progress = 10
    job.message = "Extracting plain text transcripts."
    session.commit()

    sleep(sleep_seconds)

    resolved_storage_service = resolve_storage_service(storage_root)
    result = extract_transcripts_for_project(
        session=session,
        project_id=job.project_id,
        uploaded_files=list_project_uploaded_files(session, job.project_id),
        storage_service=resolved_storage_service,
    )

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Extracted {result.success_count} transcript file(s)."
    session.commit()


def transcribe_media_for_project(
    session: Session,
    project_id: str,
    job: Job,
    speech_service: object | None = None,
) -> ExtractionResult:
    from app.services.speech_transcription import (
        OCISpeechTranscriptionService,
        format_speech_output_prefix,
        is_media_upload,
    )

    settings = get_settings()
    if settings.STORAGE_BACKEND.strip().lower() != "oci":
        raise ValueError(
            "OCI Speech transcription requires STORAGE_BACKEND=oci because "
            "media input must be available in Object Storage."
        )

    resolved_speech_service = speech_service or OCISpeechTranscriptionService(settings)
    result = ExtractionResult()
    media_files = [
        uploaded_file
        for uploaded_file in list_project_uploaded_files(session, project_id)
        if is_media_upload(uploaded_file)
    ]

    if not media_files:
        return result

    speech_job_summaries: list[str] = []
    for uploaded_file in media_files:
        output_prefix = format_speech_output_prefix(
            settings.OCI_SPEECH_OUTPUT_PREFIX,
            project_id,
            job.id,
            uploaded_file.id,
        )
        speech_job_id = resolved_speech_service.submit_transcription_job(
            uploaded_file,
            output_prefix,
        )
        speech_job_summaries.append(f"{uploaded_file.original_filename}={speech_job_id}")
        job.message = (
            "OCI Speech transcription submitted. "
            f"Speech jobs: {', '.join(speech_job_summaries)}."
        )
        session.commit()

        speech_job_status = resolved_speech_service.wait_for_completion(
            speech_job_id,
            timeout_seconds=settings.OCI_SPEECH_TIMEOUT_SECONDS,
            poll_interval_seconds=settings.OCI_SPEECH_POLL_INTERVAL_SECONDS,
        )
        if speech_job_status != "SUCCEEDED":
            raise RuntimeError(
                f"OCI Speech transcription job {speech_job_id} ended with "
                f"status {speech_job_status}."
            )

        output = resolved_speech_service.read_transcription_output(
            speech_job_id,
            speech_job_status,
            output_prefix,
        )
        extracted_content = ExtractedContent(
            project_id=project_id,
            uploaded_file_id=uploaded_file.id,
            content_type="transcript",
            title=f"{uploaded_file.original_filename} transcript",
            text_content=output.transcript_text,
            json_content=json.dumps(
                {
                    "speech_job_id": output.speech_job_id,
                    "speech_job_status": output.speech_job_status,
                    "speech_model_type": output.model_type,
                    "speech_language_code": output.language_code,
                    "source_media_file_id": uploaded_file.id,
                    "source_media_filename": uploaded_file.original_filename,
                    "output_prefix": output.output_prefix,
                    "output_object_name": output.output_object_name,
                    "timestamps": output.timestamps,
                }
            ),
        )
        session.add(extracted_content)
        result.record_success()

    return result


def process_transcribe_media_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
    speech_service: object | None = None,
) -> None:
    job.status = "running"
    job.progress = 10
    job.message = "Starting OCI Speech transcription."
    session.commit()

    sleep(sleep_seconds)

    result = transcribe_media_for_project(
        session=session,
        project_id=job.project_id,
        job=job,
        speech_service=speech_service,
    )

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Transcribed {result.success_count} media file(s)."
    session.commit()


def should_extract_docx(uploaded_file: UploadedFile) -> bool:
    extension = Path(uploaded_file.original_filename).suffix.lower()
    return uploaded_file.file_type == "docx" or extension == ".docx"


def extract_docx_for_project(
    session: Session,
    project_id: str,
    uploaded_files: list[UploadedFile],
    storage_service: StorageService,
    continue_on_error: bool = False,
) -> ExtractionResult:
    result = ExtractionResult()
    docx_files = [
        uploaded_file
        for uploaded_file in uploaded_files
        if should_extract_docx(uploaded_file)
    ]

    for uploaded_file in docx_files:
        try:
            from app.services.docx_extraction import extract_docx

            with TemporaryDirectory() as temporary_dir:
                work_dir = Path(temporary_dir)
                file_path = materialize_storage_file(
                    storage_service,
                    uploaded_file.storage_path,
                    work_dir,
                    uploaded_file.original_filename,
                )
                image_storage_prefix = (
                    f"projects/{project_id}/extracted_images/{uploaded_file.id}"
                )
                image_output_dir = work_dir / "extracted_images"
                extracted_docx = extract_docx(
                    file_path,
                    image_output_dir=image_output_dir,
                    image_storage_prefix=image_storage_prefix,
                )
                for image_storage_path in extracted_docx["json_content"].get(
                    "image_paths",
                    [],
                ):
                    image_path = image_output_dir / Path(image_storage_path).name
                    storage_service.write_file(image_storage_path, image_path)

            json_content = extracted_docx["json_content"]
            json_content["source_role"] = uploaded_file.source_role

            if uploaded_file.source_role == "fdd":
                json_content["is_golden_source"] = True

            extracted_content = ExtractedContent(
                project_id=project_id,
                uploaded_file_id=uploaded_file.id,
                content_type="docx",
                title=uploaded_file.original_filename,
                text_content=extracted_docx["text_content"],
                json_content=json.dumps(json_content),
            )
            session.add(extracted_content)
            result.record_success()
        except Exception as error:
            raise_or_record_extraction_error(
                result,
                uploaded_file,
                error,
                continue_on_error,
            )

    return result


def process_extract_docx_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
    storage_root: Path | None = None,
) -> None:
    job.status = "running"
    job.progress = 10
    job.message = "Extracting DOCX content."
    session.commit()

    sleep(sleep_seconds)

    resolved_storage_service = resolve_storage_service(storage_root)
    result = extract_docx_for_project(
        session=session,
        project_id=job.project_id,
        uploaded_files=list_project_uploaded_files(session, job.project_id),
        storage_service=resolved_storage_service,
    )

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Extracted {result.success_count} DOCX file(s)."
    session.commit()


def should_extract_pptx(uploaded_file: UploadedFile) -> bool:
    extension = Path(uploaded_file.original_filename).suffix.lower()
    return uploaded_file.file_type == "pptx" or extension == ".pptx"


def extract_pptx_for_project(
    session: Session,
    project_id: str,
    uploaded_files: list[UploadedFile],
    storage_service: StorageService,
    continue_on_error: bool = False,
) -> ExtractionResult:
    result = ExtractionResult()
    pptx_files = [
        uploaded_file
        for uploaded_file in uploaded_files
        if should_extract_pptx(uploaded_file)
    ]

    for uploaded_file in pptx_files:
        try:
            from app.services.pptx_extraction import extract_pptx

            image_storage_prefix = (
                f"projects/{project_id}/extracted_images/{uploaded_file.id}"
            )
            with TemporaryDirectory() as temporary_dir:
                work_dir = Path(temporary_dir)
                file_path = materialize_storage_file(
                    storage_service,
                    uploaded_file.storage_path,
                    work_dir,
                    uploaded_file.original_filename,
                )
                image_output_dir = work_dir / "extracted_images"
                extracted_pptx = extract_pptx(
                    file_path=file_path,
                    image_output_dir=image_output_dir,
                    image_storage_prefix=image_storage_prefix,
                )
                for image_storage_path in extracted_pptx["json_content"].get(
                    "image_paths",
                    [],
                ):
                    image_path = image_output_dir / Path(image_storage_path).name
                    storage_service.write_file(image_storage_path, image_path)

            json_content = extracted_pptx["json_content"]
            json_content["source_role"] = uploaded_file.source_role

            extracted_content = ExtractedContent(
                project_id=project_id,
                uploaded_file_id=uploaded_file.id,
                content_type="pptx",
                title=uploaded_file.original_filename,
                text_content=extracted_pptx["text_content"],
                json_content=json.dumps(json_content),
            )
            session.add(extracted_content)
            result.record_success()
        except Exception as error:
            raise_or_record_extraction_error(
                result,
                uploaded_file,
                error,
                continue_on_error,
            )

    return result


def process_extract_pptx_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
    storage_root: Path | None = None,
) -> None:
    job.status = "running"
    job.progress = 10
    job.message = "Extracting PPTX content."
    session.commit()

    sleep(sleep_seconds)

    resolved_storage_service = resolve_storage_service(storage_root)
    result = extract_pptx_for_project(
        session=session,
        project_id=job.project_id,
        uploaded_files=list_project_uploaded_files(session, job.project_id),
        storage_service=resolved_storage_service,
    )

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Extracted {result.success_count} PPTX file(s)."
    session.commit()


def should_extract_spreadsheet(uploaded_file: UploadedFile) -> bool:
    extension = Path(uploaded_file.original_filename).suffix.lower()
    return uploaded_file.file_type == "spreadsheet" or extension in {".xlsx", ".xlsm"}


def extract_spreadsheets_for_project(
    session: Session,
    project_id: str,
    uploaded_files: list[UploadedFile],
    storage_service: StorageService,
    max_rows_per_sheet: int,
    continue_on_error: bool = False,
) -> ExtractionResult:
    result = ExtractionResult()
    spreadsheet_files = [
        uploaded_file
        for uploaded_file in uploaded_files
        if should_extract_spreadsheet(uploaded_file)
    ]

    for uploaded_file in spreadsheet_files:
        try:
            from app.services.spreadsheet_extraction import extract_spreadsheet

            with TemporaryDirectory() as temporary_dir:
                file_path = materialize_storage_file(
                    storage_service,
                    uploaded_file.storage_path,
                    Path(temporary_dir),
                    uploaded_file.original_filename,
                )
                extracted_spreadsheet = extract_spreadsheet(
                    file_path=file_path,
                    max_rows_per_sheet=max_rows_per_sheet,
                )

            json_content = extracted_spreadsheet["json_content"]
            json_content["source_role"] = uploaded_file.source_role

            extracted_content = ExtractedContent(
                project_id=project_id,
                uploaded_file_id=uploaded_file.id,
                content_type="spreadsheet",
                title=uploaded_file.original_filename,
                text_content=extracted_spreadsheet["text_content"],
                json_content=json.dumps(json_content),
            )
            session.add(extracted_content)
            result.record_success()
        except Exception as error:
            raise_or_record_extraction_error(
                result,
                uploaded_file,
                error,
                continue_on_error,
            )

    return result


def process_extract_spreadsheets_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
    storage_root: Path | None = None,
    max_rows_per_sheet: int | None = None,
) -> None:
    job.status = "running"
    job.progress = 10
    job.message = "Extracting spreadsheet content."
    session.commit()

    sleep(sleep_seconds)

    resolved_storage_service = resolve_storage_service(storage_root)
    resolved_max_rows = (
        max_rows_per_sheet or get_settings().MAX_SPREADSHEET_ROWS_PER_SHEET
    )
    result = extract_spreadsheets_for_project(
        session=session,
        project_id=job.project_id,
        uploaded_files=list_project_uploaded_files(session, job.project_id),
        storage_service=resolved_storage_service,
        max_rows_per_sheet=resolved_max_rows,
    )

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Extracted {result.success_count} spreadsheet file(s)."
    session.commit()


def has_existing_document_understanding_extraction(
    session: Session,
    uploaded_file_id: str,
) -> bool:
    from app.services.document_intelligence import DOCUMENT_UNDERSTANDING_CONTENT_TYPE

    existing_extraction = session.scalar(
        select(ExtractedContent).where(
            ExtractedContent.uploaded_file_id == uploaded_file_id,
            ExtractedContent.content_type == DOCUMENT_UNDERSTANDING_CONTENT_TYPE,
        )
    )
    return existing_extraction is not None


def has_existing_non_document_understanding_extraction(
    session: Session,
    project_id: str,
) -> bool:
    from app.services.document_intelligence import DOCUMENT_UNDERSTANDING_CONTENT_TYPE

    existing_extraction = session.scalar(
        select(ExtractedContent).where(
            ExtractedContent.project_id == project_id,
            ExtractedContent.content_type != DOCUMENT_UNDERSTANDING_CONTENT_TYPE,
        )
    )
    return existing_extraction is not None


def enrich_documents_with_document_understanding(
    session: Session,
    project_id: str,
    job: Job,
    document_intelligence_service: object | None = None,
) -> ExtractionResult:
    from app.services.document_intelligence import (
        DOCUMENT_UNDERSTANDING_CONTENT_TYPE,
        NoOpDocumentIntelligenceService,
        get_document_intelligence_service,
        is_document_understanding_eligible,
    )

    settings = get_settings()
    resolved_service = (
        document_intelligence_service or get_document_intelligence_service()
    )
    result = ExtractionResult()

    if isinstance(resolved_service, NoOpDocumentIntelligenceService):
        return result

    uploaded_files = list_project_uploaded_files(session, project_id)
    eligible_files = [
        uploaded_file
        for uploaded_file in uploaded_files
        if is_document_understanding_eligible(uploaded_file, settings)
        and not has_existing_document_understanding_extraction(session, uploaded_file.id)
    ]

    for uploaded_file in eligible_files:
        try:
            job.message = (
                "Running OCI Document Understanding for "
                f"{uploaded_file.original_filename}."
            )
            session.commit()

            normalized_result = resolved_service.analyze_document(
                project_id=project_id,
                uploaded_file=uploaded_file,
                job_id=job.id,
            )
            if normalized_result is None:
                continue

            extracted_content = ExtractedContent(
                project_id=project_id,
                uploaded_file_id=uploaded_file.id,
                content_type=DOCUMENT_UNDERSTANDING_CONTENT_TYPE,
                title=(
                    f"{uploaded_file.original_filename} - "
                    "OCI Document Understanding"
                ),
                text_content=normalized_result.get("text") or "",
                json_content=json.dumps(
                    {
                        "provider": "oci_document_understanding",
                        "processor_job_id": normalized_result.get("processor_job_id"),
                        "document_metadata": normalized_result.get(
                            "document_metadata",
                            {},
                        ),
                        "pages": normalized_result.get("pages", []),
                        "detected_document_types": normalized_result.get(
                            "detected_document_types",
                            [],
                        ),
                        "tables": normalized_result.get("tables", []),
                        "raw_result_object_path": normalized_result.get(
                            "raw_result_object_path",
                        ),
                        "source_uploaded_file_id": uploaded_file.id,
                    }
                ),
            )
            session.add(extracted_content)
            result.record_success()
        except Exception as error:
            result.record_error(uploaded_file, error)

    return result


def process_enrich_document_understanding_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
    document_intelligence_service: object | None = None,
) -> None:
    job.status = "running"
    job.progress = 10
    job.message = "Starting Document Understanding enrichment."
    session.commit()

    sleep(sleep_seconds)

    result = enrich_documents_with_document_understanding(
        session=session,
        project_id=job.project_id,
        job=job,
        document_intelligence_service=document_intelligence_service,
    )

    sleep(sleep_seconds)

    job.progress = 100
    if result.attempted_count == 0:
        job.status = "completed"
        job.message = "No eligible files found for Document Understanding enrichment."
    elif result.errors and result.success_count > 0:
        job.status = "completed_with_warnings"
        job.message = (
            f"Enriched {result.success_count} of {result.attempted_count} file(s). "
            "Warnings: "
            + "; ".join(result.errors)
        )
    elif result.errors and result.success_count == 0:
        if has_existing_non_document_understanding_extraction(session, job.project_id):
            job.status = "completed_with_warnings"
            job.message = (
                f"Failed to enrich {result.attempted_count} file(s), but existing "
                "extraction remains usable. Warnings: "
                + "; ".join(result.errors)
            )
        else:
            job.status = "failed"
            job.message = (
                f"Failed to enrich {result.attempted_count} file(s). Warnings: "
                + "; ".join(result.errors)
            )
    else:
        job.status = "completed"
        job.message = f"Enriched {result.success_count} file(s)."

    session.commit()


def merge_extraction_results(results: list[ExtractionResult]) -> ExtractionResult:
    merged = ExtractionResult()

    for result in results:
        merged.attempted_count += result.attempted_count
        merged.success_count += result.success_count
        merged.errors.extend(result.errors)

    return merged


def build_extract_all_message(result: ExtractionResult) -> str:
    if result.attempted_count == 0:
        return "No extractable files found."

    summary = (
        f"Extracted {result.success_count} of {result.attempted_count} file(s) "
        "across all supported file types."
    )

    if not result.errors:
        return summary

    return f"{summary} Warnings: " + "; ".join(result.errors)


def process_extract_all_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
    storage_root: Path | None = None,
    max_rows_per_sheet: int | None = None,
) -> None:
    job.status = "running"
    job.progress = 5
    job.message = "Starting extraction for all supported files."
    session.commit()

    sleep(sleep_seconds)

    resolved_storage_service = resolve_storage_service(storage_root)
    resolved_max_rows = (
        max_rows_per_sheet or get_settings().MAX_SPREADSHEET_ROWS_PER_SHEET
    )
    uploaded_files = list_project_uploaded_files(session, job.project_id)
    stage_results: list[ExtractionResult] = []

    stages = [
        (
            "Extracting transcript text files.",
            25,
            lambda: extract_transcripts_for_project(
                session=session,
                project_id=job.project_id,
                uploaded_files=uploaded_files,
                storage_service=resolved_storage_service,
                continue_on_error=True,
            ),
        ),
        (
            "Extracting DOCX files.",
            50,
            lambda: extract_docx_for_project(
                session=session,
                project_id=job.project_id,
                uploaded_files=uploaded_files,
                storage_service=resolved_storage_service,
                continue_on_error=True,
            ),
        ),
        (
            "Extracting PPTX files.",
            75,
            lambda: extract_pptx_for_project(
                session=session,
                project_id=job.project_id,
                uploaded_files=uploaded_files,
                storage_service=resolved_storage_service,
                continue_on_error=True,
            ),
        ),
        (
            "Extracting spreadsheet files.",
            95,
            lambda: extract_spreadsheets_for_project(
                session=session,
                project_id=job.project_id,
                uploaded_files=uploaded_files,
                storage_service=resolved_storage_service,
                max_rows_per_sheet=resolved_max_rows,
                continue_on_error=True,
            ),
        ),
    ]

    for stage_message, stage_progress, run_stage in stages:
        job.message = stage_message
        session.commit()
        stage_results.append(run_stage())
        job.progress = stage_progress
        session.commit()
        sleep(sleep_seconds)

    result = merge_extraction_results(stage_results)
    job.progress = 100
    job.message = build_extract_all_message(result)

    if result.errors and result.success_count > 0:
        job.status = "completed_with_warnings"
    elif result.errors and result.success_count == 0:
        job.status = "failed"
    else:
        job.status = "completed"

    session.commit()


def process_generate_aud_plan_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
) -> None:
    from app.services.aud_plan_service import generate_aud_plan

    job.status = "running"
    job.progress = 10
    job.message = "Generating AUD plan."
    session.commit()

    sleep(sleep_seconds)

    aud_plan = generate_aud_plan(session, job.project_id)

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Generated AUD plan {aud_plan.id}."
    session.commit()


def process_build_evidence_index_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
) -> None:
    from app.services.evidence_index import build_evidence_index

    job.status = "running"
    job.progress = 10
    job.message = "Building normalized evidence index."
    session.commit()

    sleep(sleep_seconds)

    evidence_items = build_evidence_index(session, job.project_id)

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Evidence index contains {len(evidence_items)} item(s)."
    session.commit()


def process_generate_source_summaries_ai_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
) -> None:
    from app.services.source_summary_service import generate_source_summaries_ai

    job.status = "running"
    job.progress = 10
    job.message = "Generating AI source summaries."
    session.commit()

    sleep(sleep_seconds)

    result = generate_source_summaries_ai(session, job.project_id)

    sleep(sleep_seconds)

    job.progress = 100

    if result.warnings and result.summaries:
        job.status = "completed_with_warnings"
        job.message = (
            f"Generated {len(result.summaries)} source summary record(s) with "
            f"{len(result.warnings)} warning(s)."
        )
    elif result.warnings and not result.summaries:
        job.status = "failed"
        job.message = (
            "AI source summary generation failed for all source group(s): "
            + "; ".join(result.warnings)
        )
    else:
        job.status = "completed"
        job.message = f"Generated {len(result.summaries)} source summary record(s)."

    session.commit()


def process_enhance_aud_plan_ai_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
) -> None:
    from app.services.aud_plan_ai_enhancement import enhance_aud_plan_ai

    job.status = "running"
    job.progress = 10
    job.message = "Enhancing AUD plan with AI."
    session.commit()

    sleep(sleep_seconds)

    aud_plan = enhance_aud_plan_ai(session, job.project_id)

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Enhanced AUD plan {aud_plan.id}."
    session.commit()


def process_build_section_evidence_packs_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
) -> None:
    from app.services.section_evidence_pack import build_section_evidence_packs

    job.status = "running"
    job.progress = 10
    job.message = "Building section evidence packs."
    session.commit()

    sleep(sleep_seconds)

    packs = build_section_evidence_packs(session, job.project_id)

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Built {len(packs)} section evidence pack(s)."
    session.commit()


def process_generate_section_drafts_ai_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
) -> None:
    from app.services.section_drafting_ai import generate_section_drafts_ai

    job.status = "running"
    job.progress = 10
    job.message = "Generating AI section drafts."
    session.commit()

    sleep(sleep_seconds)

    result = generate_section_drafts_ai(session, job.project_id)

    sleep(sleep_seconds)

    job.progress = 100
    if result.warnings and result.drafts:
        job.status = "completed_with_warnings"
        job.message = (
            f"Generated {len(result.drafts)} section draft(s) with "
            f"{len(result.warnings)} warning(s)."
        )
    elif result.warnings and not result.drafts:
        job.status = "failed"
        job.message = (
            "AI section draft generation failed for all section(s): "
            + "; ".join(result.warnings)
        )
    else:
        job.status = "completed"
        job.message = f"Generated {len(result.drafts)} section draft(s)."

    session.commit()


def process_extract_open_points_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
) -> None:
    from app.services.open_points_service import extract_open_points

    job.status = "running"
    job.progress = 10
    job.message = "Extracting open points."
    session.commit()

    sleep(sleep_seconds)

    open_points = extract_open_points(session, job.project_id)

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Extracted {len(open_points)} open point(s)."
    session.commit()


def process_refine_open_points_ai_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
) -> None:
    from app.services.open_points_ai_refinement import refine_open_points_ai

    job.status = "running"
    job.progress = 10
    job.message = "Refining Open Points with AI."
    session.commit()

    sleep(sleep_seconds)

    result = refine_open_points_ai(session, job.project_id)

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = (
        f"Refined {len(result.open_points)} open point(s); "
        f"excluded {len(result.excluded_items)} item(s)."
    )
    session.commit()


def process_generate_docx_job(
    session: Session,
    job: Job,
    sleep_seconds: float = 0.2,
) -> None:
    from app.services.docx_generation import generate_docx, parse_docx_generation_options

    options = parse_docx_generation_options(job.message)
    job.status = "running"
    job.progress = 10
    job.message = "Generating DOCX draft."
    session.commit()

    sleep(sleep_seconds)

    generated_document = generate_docx(
        session,
        job.project_id,
        options=options,
    )

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Generated DOCX document {generated_document.id}."
    session.commit()


def process_pending_jobs(sleep_seconds: float = 0.2) -> int:
    create_db_and_tables()
    processed_count = 0

    with SessionLocal() as session:
        pending_jobs = session.scalars(
            select(Job)
            .where(
                Job.status.in_(["pending", "running"]),
                Job.job_type.in_(
                    [
                        "classify_files",
                        "extract_transcripts",
                        "transcribe_media",
                        "extract_docx",
                        "extract_pptx",
                        "extract_spreadsheets",
                        "enrich_with_document_understanding",
                        "extract_all",
                        "generate_aud_plan",
                        "build_evidence_index",
                        "generate_source_summaries_ai",
                        "enhance_aud_plan_ai",
                        "build_section_evidence_packs",
                        "generate_section_drafts_ai",
                        "extract_open_points",
                        "refine_open_points_ai",
                        "generate_docx",
                    ]
                ),
            )
            .order_by(Job.created_at.asc())
        ).all()

        for job in pending_jobs:
            try:
                if job.job_type == "classify_files":
                    process_classify_files_job(session, job, sleep_seconds=sleep_seconds)
                elif job.job_type == "extract_transcripts":
                    process_extract_transcripts_job(
                        session,
                        job,
                        sleep_seconds=sleep_seconds,
                    )
                elif job.job_type == "transcribe_media":
                    process_transcribe_media_job(
                        session,
                        job,
                        sleep_seconds=sleep_seconds,
                    )
                elif job.job_type == "extract_docx":
                    process_extract_docx_job(session, job, sleep_seconds=sleep_seconds)
                elif job.job_type == "extract_pptx":
                    process_extract_pptx_job(session, job, sleep_seconds=sleep_seconds)
                elif job.job_type == "extract_spreadsheets":
                    process_extract_spreadsheets_job(
                        session,
                        job,
                        sleep_seconds=sleep_seconds,
                    )
                elif job.job_type == "enrich_with_document_understanding":
                    process_enrich_document_understanding_job(
                        session,
                        job,
                        sleep_seconds=sleep_seconds,
                    )
                elif job.job_type == "extract_all":
                    process_extract_all_job(session, job, sleep_seconds=sleep_seconds)
                elif job.job_type == "generate_aud_plan":
                    process_generate_aud_plan_job(
                        session,
                        job,
                        sleep_seconds=sleep_seconds,
                    )
                elif job.job_type == "build_evidence_index":
                    process_build_evidence_index_job(
                        session,
                        job,
                        sleep_seconds=sleep_seconds,
                    )
                elif job.job_type == "generate_source_summaries_ai":
                    process_generate_source_summaries_ai_job(
                        session,
                        job,
                        sleep_seconds=sleep_seconds,
                    )
                elif job.job_type == "enhance_aud_plan_ai":
                    process_enhance_aud_plan_ai_job(
                        session,
                        job,
                        sleep_seconds=sleep_seconds,
                    )
                elif job.job_type == "build_section_evidence_packs":
                    process_build_section_evidence_packs_job(
                        session,
                        job,
                        sleep_seconds=sleep_seconds,
                    )
                elif job.job_type == "generate_section_drafts_ai":
                    process_generate_section_drafts_ai_job(
                        session,
                        job,
                        sleep_seconds=sleep_seconds,
                    )
                elif job.job_type == "extract_open_points":
                    process_extract_open_points_job(
                        session,
                        job,
                        sleep_seconds=sleep_seconds,
                    )
                elif job.job_type == "refine_open_points_ai":
                    process_refine_open_points_ai_job(
                        session,
                        job,
                        sleep_seconds=sleep_seconds,
                    )
                elif job.job_type == "generate_docx":
                    process_generate_docx_job(
                        session,
                        job,
                        sleep_seconds=sleep_seconds,
                    )
            except Exception as error:
                session.rollback()
                job.status = "failed"
                job.message = "".join(format_exception_only(type(error), error)).strip()
                session.commit()
            processed_count += 1

    return processed_count


def main() -> None:
    processed_count = process_pending_jobs()
    print(f"Processed {processed_count} pending job(s).")


if __name__ == "__main__":
    main()

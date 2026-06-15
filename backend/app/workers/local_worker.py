import json
from pathlib import Path
from time import sleep

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, create_db_and_tables
from app.models import ExtractedContent, Job, UploadedFile
from app.services.file_storage import get_local_storage_root

FILE_TYPE_BY_EXTENSION = {
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "spreadsheet",
    ".xlsm": "spreadsheet",
    ".txt": "transcript_text",
    ".m4a": "media",
    ".mp4": "media",
    ".pdf": "pdf",
}


def classify_file_type(filename: str) -> str | None:
    return FILE_TYPE_BY_EXTENSION.get(Path(filename).suffix.lower())


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


def read_uploaded_text_file(storage_root: Path, uploaded_file: UploadedFile) -> str:
    file_path = storage_root / uploaded_file.storage_path
    return file_path.read_text(encoding="utf-8", errors="replace")


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

    resolved_storage_root = storage_root or get_local_storage_root()
    uploaded_files = session.scalars(
        select(UploadedFile).where(UploadedFile.project_id == job.project_id)
    ).all()
    transcript_files = [
        uploaded_file
        for uploaded_file in uploaded_files
        if should_extract_transcript(uploaded_file)
    ]

    for uploaded_file in transcript_files:
        text_content = read_uploaded_text_file(resolved_storage_root, uploaded_file)
        extracted_content = ExtractedContent(
            project_id=job.project_id,
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

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Extracted {len(transcript_files)} transcript file(s)."
    session.commit()


def should_extract_docx(uploaded_file: UploadedFile) -> bool:
    extension = Path(uploaded_file.original_filename).suffix.lower()
    return uploaded_file.file_type == "docx" or extension == ".docx"


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

    resolved_storage_root = storage_root or get_local_storage_root()
    uploaded_files = session.scalars(
        select(UploadedFile).where(UploadedFile.project_id == job.project_id)
    ).all()
    docx_files = [
        uploaded_file
        for uploaded_file in uploaded_files
        if should_extract_docx(uploaded_file)
    ]

    for uploaded_file in docx_files:
        from app.services.docx_extraction import extract_docx

        file_path = resolved_storage_root / uploaded_file.storage_path
        extracted_docx = extract_docx(file_path)
        json_content = extracted_docx["json_content"]
        json_content["source_role"] = uploaded_file.source_role

        if uploaded_file.source_role == "fdd":
            json_content["is_golden_source"] = True

        extracted_content = ExtractedContent(
            project_id=job.project_id,
            uploaded_file_id=uploaded_file.id,
            content_type="docx",
            title=uploaded_file.original_filename,
            text_content=extracted_docx["text_content"],
            json_content=json.dumps(json_content),
        )
        session.add(extracted_content)

    sleep(sleep_seconds)

    job.status = "completed"
    job.progress = 100
    job.message = f"Extracted {len(docx_files)} DOCX file(s)."
    session.commit()


def process_pending_jobs(sleep_seconds: float = 0.2) -> int:
    create_db_and_tables()
    processed_count = 0

    with SessionLocal() as session:
        pending_jobs = session.scalars(
            select(Job)
            .where(
                Job.status == "pending",
                Job.job_type.in_(
                    ["classify_files", "extract_transcripts", "extract_docx"]
                ),
            )
            .order_by(Job.created_at.asc())
        ).all()

        for job in pending_jobs:
            if job.job_type == "classify_files":
                process_classify_files_job(session, job, sleep_seconds=sleep_seconds)
            elif job.job_type == "extract_transcripts":
                process_extract_transcripts_job(session, job, sleep_seconds=sleep_seconds)
            elif job.job_type == "extract_docx":
                process_extract_docx_job(session, job, sleep_seconds=sleep_seconds)
            processed_count += 1

    return processed_count


def main() -> None:
    processed_count = process_pending_jobs()
    print(f"Processed {processed_count} pending job(s).")


if __name__ == "__main__":
    main()

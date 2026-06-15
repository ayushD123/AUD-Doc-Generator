from pathlib import Path
from time import sleep

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, create_db_and_tables
from app.models import Job, UploadedFile

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


def process_classify_files_job(session: Session, job: Job, sleep_seconds: float = 0.2) -> None:
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


def process_pending_jobs(sleep_seconds: float = 0.2) -> int:
    create_db_and_tables()
    processed_count = 0

    with SessionLocal() as session:
        pending_jobs = session.scalars(
            select(Job)
            .where(Job.status == "pending", Job.job_type == "classify_files")
            .order_by(Job.created_at.asc())
        ).all()

        for job in pending_jobs:
            process_classify_files_job(session, job, sleep_seconds=sleep_seconds)
            processed_count += 1

    return processed_count


def main() -> None:
    processed_count = process_pending_jobs()
    print(f"Processed {processed_count} pending job(s).")


if __name__ == "__main__":
    main()

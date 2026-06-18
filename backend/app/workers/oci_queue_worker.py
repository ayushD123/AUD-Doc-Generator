from __future__ import annotations

import json
from traceback import format_exception_only
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal, create_db_and_tables
from app.models import Job
from app.services.job_queue import OCIJobQueueService
from app.workers.local_worker import (
    process_classify_files_job,
    process_extract_all_job,
    process_extract_docx_job,
    process_extract_open_points_job,
    process_extract_pptx_job,
    process_extract_spreadsheets_job,
    process_extract_transcripts_job,
    process_generate_aud_plan_job,
    process_generate_docx_job,
    process_transcribe_media_job,
)


JobProcessor = Callable[..., None]


JOB_PROCESSORS: dict[str, JobProcessor] = {
    "classify_files": process_classify_files_job,
    "extract_transcripts": process_extract_transcripts_job,
    "transcribe_media": process_transcribe_media_job,
    "extract_docx": process_extract_docx_job,
    "extract_pptx": process_extract_pptx_job,
    "extract_spreadsheets": process_extract_spreadsheets_job,
    "extract_all": process_extract_all_job,
    "generate_aud_plan": process_generate_aud_plan_job,
    "extract_open_points": process_extract_open_points_job,
    "generate_docx": process_generate_docx_job,
}


class UnrecoverableQueueMessageError(Exception):
    pass


def parse_queue_message_content(message: object) -> dict[str, Any]:
    content = getattr(message, "content", message)
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    if not isinstance(content, str):
        raise ValueError("OCI Queue message content must be a JSON string.")

    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("OCI Queue message payload must be a JSON object.")

    return payload


def get_message_receipt(message: object) -> str:
    receipt = getattr(message, "receipt", None)
    if not receipt:
        raise ValueError("OCI Queue message receipt is required for deletion.")

    return receipt


def mark_job_failed(session: Session, job: Job, error: Exception) -> None:
    session.rollback()
    job.status = "failed"
    job.message = "".join(format_exception_only(type(error), error)).strip()
    session.commit()


def process_job_by_id(
    session: Session,
    job_id: str,
    sleep_seconds: float = 0.2,
) -> None:
    job = session.get(Job, job_id)
    if job is None:
        raise UnrecoverableQueueMessageError(f"Job {job_id} not found.")

    processor = JOB_PROCESSORS.get(job.job_type)
    if processor is None:
        raise UnrecoverableQueueMessageError(
            f"Unsupported job type: {job.job_type}."
        )

    try:
        processor(session, job, sleep_seconds=sleep_seconds)
    except Exception as error:
        mark_job_failed(session, job, error)
        raise


def build_queue_client(settings: Settings) -> object:
    return OCIJobQueueService(settings=settings).client


def get_messages(
    client: object,
    queue_id: str,
    limit: int = 10,
    visibility_in_seconds: int = 300,
) -> list[object]:
    response = client.get_messages(
        queue_id,
        limit=limit,
        visibility_in_seconds=visibility_in_seconds,
    )
    return list(getattr(response.data, "messages", []))


def delete_message(client: object, queue_id: str, message: object) -> None:
    client.delete_message(queue_id, get_message_receipt(message))


def mark_message_skipped(message: object, reason: str) -> None:
    setattr(message, "skip_reason", reason)


def process_oci_queue_messages(
    client: object | None = None,
    settings: Settings | None = None,
    max_messages: int = 10,
    sleep_seconds: float = 0.2,
) -> int:
    create_db_and_tables()
    resolved_settings = settings or get_settings()
    queue_id = OCIJobQueueService.require_setting(
        resolved_settings.OCI_QUEUE_OCID,
        "OCI_QUEUE_OCID",
    )
    queue_client = client or build_queue_client(resolved_settings)
    processed_count = 0

    with SessionLocal() as session:
        for message in get_messages(queue_client, queue_id, limit=max_messages):
            should_delete_message = False
            try:
                payload = parse_queue_message_content(message)
                job_id = payload.get("job_id")
                if not job_id:
                    raise UnrecoverableQueueMessageError(
                        "OCI Queue message payload is missing job_id."
                    )

                process_job_by_id(
                    session,
                    str(job_id),
                    sleep_seconds=sleep_seconds,
                )
                processed_count += 1
                should_delete_message = True
            except (json.JSONDecodeError, UnrecoverableQueueMessageError) as error:
                mark_message_skipped(message, str(error))
                should_delete_message = True
            finally:
                if should_delete_message:
                    delete_message(queue_client, queue_id, message)

    return processed_count


def main() -> None:
    processed_count = process_oci_queue_messages()
    print(f"Processed {processed_count} OCI queued job(s).")


if __name__ == "__main__":
    main()

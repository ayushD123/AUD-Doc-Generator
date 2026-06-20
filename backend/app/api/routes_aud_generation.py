from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes_jobs import publish_created_job
from app.db.session import get_db
from app.models import Job, Project
from app.schemas.aud_generation import (
    AUDGenerationStartRead,
    AUDGenerationStatusRead,
)
from app.services.aud_pipeline_orchestrator import (
    find_latest_generation_run,
    get_or_create_generation_run,
    parse_json_list,
)
from app.services.job_queue import JobQueueService, get_job_queue_service

router = APIRouter(prefix="/projects/{project_id}/generate-aud", tags=["aud-generation"])


def resume_failed_generation_run(
    generation_run_id: str,
    db: Session,
    queue_service: JobQueueService,
) -> Job | None:
    job = db.get(Job, generation_run_id)
    if job is None or job.job_type != "generate_aud":
        return None

    generation_run = get_or_create_generation_run(
        db,
        project_id=job.project_id,
        run_id=job.id,
    )
    generation_run.status = "queued"
    generation_run.current_stage = None
    generation_run.failed_stage = None
    generation_run.error_message = None
    generation_run.completed_at = None
    job.status = "pending"
    job.progress = 0
    job.message = "AUD generation retry queued."
    db.commit()
    db.refresh(job)
    publish_created_job(job, db, queue_service)
    db.refresh(job)
    return job


@router.post("", response_model=AUDGenerationStartRead, status_code=status.HTTP_202_ACCEPTED)
def start_aud_generation(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    queue_service: Annotated[JobQueueService, Depends(get_job_queue_service)],
) -> AUDGenerationStartRead:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    latest_run = find_latest_generation_run(db, project_id)
    if latest_run is not None and latest_run.status == "failed":
        resumed_job = resume_failed_generation_run(
            latest_run.id,
            db,
            queue_service,
        )
        if resumed_job is not None:
            return AUDGenerationStartRead(
                job_id=resumed_job.id,
                status="queued",
                message="AUD generation started",
            )

    job = Job(
        project_id=project_id,
        job_type="generate_aud",
        message="AUD generation started.",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    generation_run = get_or_create_generation_run(
        db,
        project_id=project_id,
        run_id=job.id,
    )
    publish_created_job(job, db, queue_service)
    db.refresh(generation_run)

    return AUDGenerationStartRead(
        job_id=job.id,
        status="queued",
        message="AUD generation started",
    )


@router.get("/status", response_model=AUDGenerationStatusRead)
def get_aud_generation_status(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> AUDGenerationStatusRead:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    generation_run = find_latest_generation_run(db, project_id)
    if generation_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AUD generation has not been started for this project.",
        )

    final_document_url = None
    if generation_run.final_document_id:
        final_document_url = (
            f"/projects/{project_id}/generated-documents/"
            f"{generation_run.final_document_id}/download"
        )

    return AUDGenerationStatusRead(
        job_id=generation_run.id,
        status=generation_run.status,
        current_stage=generation_run.current_stage,
        completed_stages=parse_json_list(generation_run.completed_stages_json),
        failed_stage=generation_run.failed_stage,
        warnings=parse_json_list(generation_run.warnings_json),
        final_document_id=generation_run.final_document_id,
        final_document_url=final_document_url,
        error=generation_run.error_message,
    )

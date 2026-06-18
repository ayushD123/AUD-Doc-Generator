from typing import Annotated
from traceback import format_exception_only

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Job, Project
from app.schemas.job import JobCreate, JobRead
from app.services.job_queue import JobQueueService, get_job_queue_service

router = APIRouter(prefix="/projects/{project_id}/jobs", tags=["jobs"])


def publish_created_job(job: Job, db: Session, queue_service: JobQueueService) -> None:
    try:
        queue_service.publish_job(job)
    except Exception as error:
        db.rollback()
        job.status = "failed"
        job.message = (
            "Failed to publish job to queue: "
            f"{''.join(format_exception_only(type(error), error)).strip()}"
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to publish job to queue.",
        ) from error


def create_project_job(
    project_id: str,
    job_type: str,
    message: str | None,
    db: Session,
    queue_service: JobQueueService,
) -> Job:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    job = Job(
        project_id=project.id,
        job_type=job_type,
        message=message,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    publish_created_job(job, db, queue_service)
    db.refresh(job)
    return job


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    project_id: str,
    payload: JobCreate,
    db: Annotated[Session, Depends(get_db)],
    queue_service: Annotated[JobQueueService, Depends(get_job_queue_service)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type=payload.job_type,
        message=payload.message,
        db=db,
        queue_service=queue_service,
    )


@router.post(
    "/classify-files",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_classify_files_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    queue_service: Annotated[JobQueueService, Depends(get_job_queue_service)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="classify_files",
        message="File classification job queued.",
        db=db,
        queue_service=queue_service,
    )


@router.post(
    "/extract-transcripts",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_extract_transcripts_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    queue_service: Annotated[JobQueueService, Depends(get_job_queue_service)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="extract_transcripts",
        message="Transcript extraction job queued.",
        db=db,
        queue_service=queue_service,
    )


@router.post(
    "/extract-docx",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_extract_docx_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    queue_service: Annotated[JobQueueService, Depends(get_job_queue_service)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="extract_docx",
        message="DOCX extraction job queued.",
        db=db,
        queue_service=queue_service,
    )


@router.post(
    "/transcribe-media",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_transcribe_media_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    queue_service: Annotated[JobQueueService, Depends(get_job_queue_service)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="transcribe_media",
        message="Media transcription job queued.",
        db=db,
        queue_service=queue_service,
    )


@router.post(
    "/extract-pptx",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_extract_pptx_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    queue_service: Annotated[JobQueueService, Depends(get_job_queue_service)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="extract_pptx",
        message="PPTX extraction job queued.",
        db=db,
        queue_service=queue_service,
    )


@router.post(
    "/extract-spreadsheets",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_extract_spreadsheets_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    queue_service: Annotated[JobQueueService, Depends(get_job_queue_service)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="extract_spreadsheets",
        message="Spreadsheet extraction job queued.",
        db=db,
        queue_service=queue_service,
    )


@router.post(
    "/extract-all",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_extract_all_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    queue_service: Annotated[JobQueueService, Depends(get_job_queue_service)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="extract_all",
        message="Extract all files job queued.",
        db=db,
        queue_service=queue_service,
    )


@router.post(
    "/generate-aud-plan",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_generate_aud_plan_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    queue_service: Annotated[JobQueueService, Depends(get_job_queue_service)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="generate_aud_plan",
        message="AUD plan generation job queued.",
        db=db,
        queue_service=queue_service,
    )


@router.post(
    "/extract-open-points",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_extract_open_points_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    queue_service: Annotated[JobQueueService, Depends(get_job_queue_service)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="extract_open_points",
        message="Open points extraction job queued.",
        db=db,
        queue_service=queue_service,
    )


@router.post(
    "/generate-docx",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_generate_docx_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    queue_service: Annotated[JobQueueService, Depends(get_job_queue_service)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="generate_docx",
        message="DOCX generation job queued.",
        db=db,
        queue_service=queue_service,
    )


@router.get("", response_model=list[JobRead])
def list_jobs(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[Job]:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    statement = (
        select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc())
    )
    return list(db.scalars(statement))

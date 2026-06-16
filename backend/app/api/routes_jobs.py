from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Job, Project
from app.schemas.job import JobCreate, JobRead

router = APIRouter(prefix="/projects/{project_id}/jobs", tags=["jobs"])


def create_project_job(
    project_id: str,
    job_type: str,
    message: str,
    db: Session,
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
    return job


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    project_id: str,
    payload: JobCreate,
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    job = Job(
        project_id=project.id,
        job_type=payload.job_type,
        message=payload.message,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post(
    "/classify-files",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_classify_files_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="classify_files",
        message="File classification job queued.",
        db=db,
    )


@router.post(
    "/extract-transcripts",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_extract_transcripts_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="extract_transcripts",
        message="Transcript extraction job queued.",
        db=db,
    )


@router.post(
    "/extract-docx",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_extract_docx_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="extract_docx",
        message="DOCX extraction job queued.",
        db=db,
    )


@router.post(
    "/extract-pptx",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_extract_pptx_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="extract_pptx",
        message="PPTX extraction job queued.",
        db=db,
    )


@router.post(
    "/extract-spreadsheets",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_extract_spreadsheets_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="extract_spreadsheets",
        message="Spreadsheet extraction job queued.",
        db=db,
    )


@router.post(
    "/extract-all",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_extract_all_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="extract_all",
        message="Extract all files job queued.",
        db=db,
    )


@router.post(
    "/generate-aud-plan",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_generate_aud_plan_job(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    return create_project_job(
        project_id=project_id,
        job_type="generate_aud_plan",
        message="AUD plan generation job queued.",
        db=db,
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

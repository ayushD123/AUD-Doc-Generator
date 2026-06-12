from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Job, Project
from app.schemas.job import JobCreate, JobRead

router = APIRouter(prefix="/projects/{project_id}/jobs", tags=["jobs"])


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

    statement = select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc())
    return list(db.scalars(statement))

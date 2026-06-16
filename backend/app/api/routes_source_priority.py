from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project
from app.schemas.source_priority import SourcePriorityReport
from app.services.source_priority_service import build_source_priority_report

router = APIRouter(
    prefix="/projects/{project_id}/source-priority-report",
    tags=["source-priority"],
)


@router.get("", response_model=SourcePriorityReport)
def get_source_priority_report(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> SourcePriorityReport:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    return build_source_priority_report(db, project_id)

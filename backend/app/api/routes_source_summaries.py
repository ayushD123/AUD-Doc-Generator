from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project, SourceSummary
from app.schemas.source_summary import SourceSummaryRead

router = APIRouter(
    prefix="/projects/{project_id}/source-summaries",
    tags=["source-summaries"],
)


@router.get("", response_model=list[SourceSummaryRead])
def list_source_summaries(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[SourceSummary]:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    statement = (
        select(SourceSummary)
        .where(SourceSummary.project_id == project_id)
        .order_by(SourceSummary.source_role.asc(), SourceSummary.created_at.asc())
    )
    return list(db.scalars(statement))

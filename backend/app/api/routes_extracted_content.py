from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ExtractedContent, Project
from app.schemas.extracted_content import ExtractedContentRead

router = APIRouter(
    prefix="/projects/{project_id}/extracted-content",
    tags=["extracted-content"],
)


@router.get("", response_model=list[ExtractedContentRead])
def list_extracted_content(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[ExtractedContent]:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    statement = (
        select(ExtractedContent)
        .where(ExtractedContent.project_id == project_id)
        .order_by(ExtractedContent.created_at.desc())
    )
    return list(db.scalars(statement))

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AUDSectionDraft, Project
from app.schemas.aud_section_draft import AUDSectionDraftRead

router = APIRouter(
    prefix="/projects/{project_id}/section-drafts",
    tags=["section-drafts"],
)


@router.get("", response_model=list[AUDSectionDraftRead])
def list_section_drafts(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[AUDSectionDraft]:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    statement = (
        select(AUDSectionDraft)
        .where(AUDSectionDraft.project_id == project_id)
        .order_by(AUDSectionDraft.created_at.asc())
    )
    return list(db.scalars(statement))

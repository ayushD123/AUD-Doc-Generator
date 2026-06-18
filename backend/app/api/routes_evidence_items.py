from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import EvidenceItem, Project
from app.schemas.evidence_item import EvidenceItemRead

router = APIRouter(
    prefix="/projects/{project_id}/evidence-items",
    tags=["evidence-items"],
)


@router.get("", response_model=list[EvidenceItemRead])
def list_evidence_items(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[EvidenceItem]:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    statement = (
        select(EvidenceItem)
        .where(EvidenceItem.project_id == project_id)
        .order_by(EvidenceItem.priority.desc(), EvidenceItem.created_at.asc())
    )
    return list(db.scalars(statement))

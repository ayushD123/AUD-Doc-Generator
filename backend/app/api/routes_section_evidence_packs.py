from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project, SectionEvidencePack
from app.schemas.section_evidence_pack import SectionEvidencePackRead

router = APIRouter(
    prefix="/projects/{project_id}/section-evidence-packs",
    tags=["section-evidence-packs"],
)


@router.get("", response_model=list[SectionEvidencePackRead])
def list_section_evidence_packs(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[SectionEvidencePack]:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    statement = (
        select(SectionEvidencePack)
        .where(SectionEvidencePack.project_id == project_id)
        .order_by(SectionEvidencePack.created_at.asc())
    )
    return list(db.scalars(statement))

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AUDPlan, Project
from app.schemas.aud_plan import AUDPlanRead

router = APIRouter(prefix="/projects/{project_id}/aud-plan", tags=["aud-plan"])


@router.get("", response_model=AUDPlanRead)
def get_aud_plan(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> AUDPlan:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    statement = (
        select(AUDPlan)
        .where(AUDPlan.project_id == project_id)
        .order_by(AUDPlan.created_at.desc())
    )
    aud_plan = db.scalars(statement).first()

    if aud_plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AUD plan not found.",
        )

    return aud_plan

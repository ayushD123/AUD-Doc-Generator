from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import OpenPoint, Project
from app.schemas.open_point import OpenPointRead

router = APIRouter(prefix="/projects/{project_id}/open-points", tags=["open-points"])


@router.get("", response_model=list[OpenPointRead])
def list_open_points(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[OpenPoint]:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    statement = (
        select(OpenPoint)
        .where(OpenPoint.project_id == project_id)
        .order_by(OpenPoint.created_at.asc())
    )
    return list(db.scalars(statement))

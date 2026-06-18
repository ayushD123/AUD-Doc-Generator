from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import OpenPoint, Project
from app.schemas.open_point import OpenPointRead
from app.services.open_points_ai_refinement import (
    get_open_point_evidence_text,
    get_refinement_metadata,
)

router = APIRouter(prefix="/projects/{project_id}/open-points", tags=["open-points"])


def to_open_point_read(open_point: OpenPoint) -> OpenPointRead:
    refinement_metadata = get_refinement_metadata(open_point.evidence)
    evidence_text = open_point.evidence

    if refinement_metadata:
        evidence_text = get_open_point_evidence_text(open_point)
        refinement_metadata = {
            key: value
            for key, value in refinement_metadata.items()
            if key != "evidence_text"
        }

    return OpenPointRead(
        id=open_point.id,
        project_id=open_point.project_id,
        topic=open_point.topic,
        question=open_point.question,
        status=open_point.status,
        source_file_id=open_point.source_file_id,
        source_content_id=open_point.source_content_id,
        evidence=evidence_text,
        refinement_metadata=refinement_metadata or None,
        created_at=open_point.created_at,
        updated_at=open_point.updated_at,
    )


@router.get("", response_model=list[OpenPointRead])
def list_open_points(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[OpenPointRead]:
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
    return [to_open_point_read(open_point) for open_point in db.scalars(statement)]

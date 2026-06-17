from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import GeneratedDocument, Project
from app.schemas.generated_document import GeneratedDocumentRead
from app.services.file_storage import get_local_storage_root

router = APIRouter(
    prefix="/projects/{project_id}/generated-documents",
    tags=["generated-documents"],
)


def get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    return project


@router.get("", response_model=list[GeneratedDocumentRead])
def list_generated_documents(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[GeneratedDocument]:
    get_project_or_404(project_id, db)

    statement = (
        select(GeneratedDocument)
        .where(GeneratedDocument.project_id == project_id)
        .order_by(GeneratedDocument.created_at.desc())
    )
    return list(db.scalars(statement))


@router.get("/{document_id}/download")
def download_generated_document(
    project_id: str,
    document_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    get_project_or_404(project_id, db)
    generated_document = db.get(GeneratedDocument, document_id)

    if (
        generated_document is None
        or generated_document.project_id != project_id
        or not generated_document.storage_path
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated document not found.",
        )

    storage_root = get_local_storage_root()
    file_path = storage_root / generated_document.storage_path
    resolved_storage_root = storage_root.resolve()
    resolved_file_path = file_path.resolve()

    if (
        resolved_storage_root not in resolved_file_path.parents
        and resolved_file_path != resolved_storage_root
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated document not found.",
        )

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated document file not found.",
        )

    return FileResponse(
        path=Path(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=generated_document.filename,
    )

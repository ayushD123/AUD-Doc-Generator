from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import GeneratedDocument, Project
from app.schemas.generated_document import GeneratedDocumentRead
from app.services.file_storage import StorageService, get_file_storage

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
    storage_service: Annotated[StorageService, Depends(get_file_storage)],
) -> Response:
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

    if not storage_service.exists(generated_document.storage_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated document file not found.",
        )

    content = storage_service.read_bytes(generated_document.storage_path)
    filename = generated_document.filename
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{filename}\"; "
                f"filename*=UTF-8''{quote(filename)}"
            )
        },
    )

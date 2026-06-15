from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project, UploadedFile
from app.schemas.uploaded_file import UploadedFileRead
from app.services.file_storage import (
    ALLOWED_FILE_EXTENSIONS,
    LocalFileStorageService,
    get_file_storage,
)

router = APIRouter(prefix="/projects/{project_id}/files", tags=["files"])

ALLOWED_SOURCE_ROLES = {
    "template_aud",
    "final_aud_sample",
    "fdd",
    "kt_ppt",
    "kt_session",
    "kt_transcript",
    "config_workbook",
    "supporting_doc",
    "unknown",
}


def validate_source_role(source_role: str | None) -> str:
    if source_role is None or source_role.strip() == "":
        return "unknown"

    normalized_source_role = source_role.strip()

    if normalized_source_role not in ALLOWED_SOURCE_ROLES:
        allowed_values = ", ".join(sorted(ALLOWED_SOURCE_ROLES))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported source_role. Allowed values: {allowed_values}.",
        )

    return normalized_source_role


def validate_file_extension(filename: str | None) -> str:
    extension = Path(filename or "").suffix.lower()

    if extension not in ALLOWED_FILE_EXTENSIONS:
        allowed_values = ", ".join(sorted(ALLOWED_FILE_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file extension. Allowed extensions: {allowed_values}.",
        )

    return extension


@router.post("", response_model=UploadedFileRead, status_code=status.HTTP_201_CREATED)
def upload_project_file(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
    storage_service: Annotated[LocalFileStorageService, Depends(get_file_storage)],
    file: UploadFile = File(...),
    source_role: str | None = Form(default=None),
) -> UploadedFile:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    validate_file_extension(file.filename)
    normalized_source_role = validate_source_role(source_role)
    storage_path, file_type = storage_service.save_project_upload(project_id, file)

    uploaded_file = UploadedFile(
        project_id=project.id,
        original_filename=file.filename or "uploaded_file",
        file_type=file_type,
        storage_path=storage_path,
        source_role=normalized_source_role,
    )
    db.add(uploaded_file)
    db.commit()
    db.refresh(uploaded_file)
    return uploaded_file


@router.get("", response_model=list[UploadedFileRead])
def list_project_files(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> list[UploadedFile]:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    statement = (
        select(UploadedFile)
        .where(UploadedFile.project_id == project_id)
        .order_by(UploadedFile.created_at.desc())
    )
    return list(db.scalars(statement))

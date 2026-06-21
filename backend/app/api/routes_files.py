from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import delete as sqlalchemy_delete
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.base import new_uuid
from app.db.session import get_db
from app.models import (
    EvidenceItem,
    ExtractedContent,
    OpenPoint,
    Project,
    SourceSummary,
    UploadedFile,
)
from app.schemas.uploaded_file import UploadedFileRead
from app.services.file_storage import (
    ALLOWED_FILE_EXTENSIONS,
    StorageService,
    get_file_storage,
)

router = APIRouter(prefix="/projects/{project_id}/files", tags=["files"])

ALLOWED_SOURCE_ROLES = {
    "aud_template",
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
    storage_service: Annotated[StorageService, Depends(get_file_storage)],
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
    uploaded_file_id = new_uuid()
    storage_path, file_type = storage_service.save_project_upload(
        project_id,
        uploaded_file_id,
        file,
    )

    uploaded_file = UploadedFile(
        id=uploaded_file_id,
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


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_file(
    project_id: str,
    file_id: str,
    db: Annotated[Session, Depends(get_db)],
    storage_service: Annotated[StorageService, Depends(get_file_storage)],
) -> None:
    project = db.get(Project, project_id)

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )

    uploaded_file = db.get(UploadedFile, file_id)

    if uploaded_file is None or uploaded_file.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded file not found.",
        )

    extracted_content_ids = list(
        db.scalars(
            select(ExtractedContent.id).where(
                ExtractedContent.project_id == project_id,
                ExtractedContent.uploaded_file_id == file_id,
            )
        )
    )

    storage_service.delete(uploaded_file.storage_path)

    evidence_conditions = [
        EvidenceItem.source_uploaded_file_id == file_id,
    ]

    if extracted_content_ids:
        evidence_conditions.append(
            EvidenceItem.source_extracted_content_id.in_(extracted_content_ids)
        )

    open_point_conditions = [
        OpenPoint.source_file_id == file_id,
    ]

    if extracted_content_ids:
        open_point_conditions.append(OpenPoint.source_content_id.in_(extracted_content_ids))

    db.execute(
        sqlalchemy_delete(EvidenceItem).where(
            EvidenceItem.project_id == project_id,
            or_(*evidence_conditions),
        )
    )
    db.execute(
        sqlalchemy_delete(SourceSummary).where(
            SourceSummary.project_id == project_id,
            SourceSummary.source_uploaded_file_id == file_id,
        )
    )
    db.execute(
        sqlalchemy_delete(OpenPoint).where(
            OpenPoint.project_id == project_id,
            or_(*open_point_conditions),
        )
    )
    db.execute(
        sqlalchemy_delete(ExtractedContent).where(
            ExtractedContent.project_id == project_id,
            ExtractedContent.uploaded_file_id == file_id,
        )
    )
    db.delete(uploaded_file)
    db.commit()

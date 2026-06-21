from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import UploadedFile
from app.services.file_storage import StorageService, get_file_storage

logger = logging.getLogger(__name__)

EXPLICIT_AUD_TEMPLATE_SOURCE_ROLES = {"aud_template", "template_aud"}


@dataclass(frozen=True)
class ResolvedTemplate:
    path: Path
    source: str
    display_path: str
    uploaded_file: UploadedFile | None = None


def get_backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_configured_template_path(
    configured_path: str,
    backend_root: Path | None = None,
) -> Path:
    root = backend_root or get_backend_root()
    normalized_configured_path = configured_path.replace("\\", "/").lstrip("/")
    if normalized_configured_path.lower().startswith("backend/"):
        return root.parent / normalized_configured_path

    raw_path = Path(configured_path)

    if raw_path.is_absolute():
        if raw_path.exists():
            return raw_path

        parts = [part for part in raw_path.parts if part not in {raw_path.anchor, "\\"}]
        if parts and parts[0].lower() == "backend":
            return root.parent.joinpath(*parts)

        return raw_path

    parts = raw_path.parts
    if parts and parts[0].lower() == "backend":
        return root.parent / raw_path

    return root / raw_path


class TemplateResolver:
    def __init__(
        self,
        session: Session,
        project_id: str,
        storage_service: StorageService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.project_id = project_id
        self.storage_service = storage_service or get_file_storage()
        self.settings = settings or get_settings()

    def resolve(self, temporary_dir: Path) -> ResolvedTemplate:
        uploaded_template = self.find_uploaded_template()
        if uploaded_template is not None:
            resolved = self.resolve_uploaded_template(uploaded_template, temporary_dir)
            logger.info("Using uploaded AUD template: %s", resolved.display_path)
            return resolved

        resolved = self.resolve_default_template()
        logger.info(
            "Using default AUD template: %s",
            self.settings.DEFAULT_AUD_TEMPLATE_PATH,
        )
        return resolved

    def find_uploaded_template(self) -> UploadedFile | None:
        statement = (
            select(UploadedFile)
            .where(
                UploadedFile.project_id == self.project_id,
                UploadedFile.source_role.in_(EXPLICIT_AUD_TEMPLATE_SOURCE_ROLES),
            )
            .order_by(UploadedFile.created_at.desc())
        )
        return self.session.scalars(statement).first()

    def resolve_uploaded_template(
        self,
        uploaded_file: UploadedFile,
        temporary_dir: Path,
    ) -> ResolvedTemplate:
        if not self.storage_service.exists(uploaded_file.storage_path):
            raise FileNotFoundError(
                "Uploaded AUD template file is missing from storage: "
                f"{uploaded_file.original_filename}."
            )

        local_path = self.storage_service.local_path(uploaded_file.storage_path)
        if local_path is None:
            local_path = temporary_dir / uploaded_file.original_filename
            self.storage_service.download_to_path(uploaded_file.storage_path, local_path)

        if not local_path.is_file():
            raise FileNotFoundError(
                "Uploaded AUD template file could not be materialized: "
                f"{uploaded_file.original_filename}."
            )

        return ResolvedTemplate(
            path=local_path,
            source="uploaded",
            display_path=uploaded_file.storage_path,
            uploaded_file=uploaded_file,
        )

    def resolve_default_template(self) -> ResolvedTemplate:
        template_path = resolve_configured_template_path(
            self.settings.DEFAULT_AUD_TEMPLATE_PATH
        )

        if not template_path.is_file():
            raise FileNotFoundError(
                "Default AUD template file not found: "
                f"{self.settings.DEFAULT_AUD_TEMPLATE_PATH}."
            )

        return ResolvedTemplate(
            path=template_path,
            source="default",
            display_path=self.settings.DEFAULT_AUD_TEMPLATE_PATH,
        )

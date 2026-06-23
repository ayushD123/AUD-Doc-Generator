from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid, utc_now
from app.db.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.evidence_item import EvidenceItem
    from app.models.extracted_content import ExtractedContent
    from app.models.project import Project
    from app.models.source_summary import SourceSummary


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
    )

    project: Mapped["Project"] = relationship(back_populates="uploaded_files")
    extracted_contents: Mapped[list["ExtractedContent"]] = relationship(
        back_populates="uploaded_file",
        cascade="all, delete-orphan",
    )
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(
        back_populates="source_uploaded_file",
    )
    source_summaries: Mapped[list["SourceSummary"]] = relationship(
        back_populates="source_uploaded_file",
    )

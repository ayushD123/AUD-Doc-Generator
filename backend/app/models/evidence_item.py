from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid, utc_now
from app.db.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.extracted_content import ExtractedContent
    from app.models.project import Project
    from app.models.uploaded_file import UploadedFile


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id"),
        nullable=False,
    )
    source_uploaded_file_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("uploaded_files.id"),
        nullable=True,
    )
    source_extracted_content_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("extracted_contents.id"),
        nullable=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    json_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    project: Mapped["Project"] = relationship(back_populates="evidence_items")
    source_uploaded_file: Mapped["UploadedFile | None"] = relationship(
        back_populates="evidence_items",
    )
    source_extracted_content: Mapped["ExtractedContent | None"] = relationship(
        back_populates="evidence_items",
    )

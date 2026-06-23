from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid, utc_now
from app.db.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.uploaded_file import UploadedFile


class SourceSummary(Base):
    __tablename__ = "source_summaries"

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
    source_role: Mapped[str] = mapped_column(String(100), nullable=False)
    summary_type: Mapped[str] = mapped_column(String(100), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    project: Mapped["Project"] = relationship(back_populates="source_summaries")
    source_uploaded_file: Mapped["UploadedFile | None"] = relationship(
        back_populates="source_summaries",
    )

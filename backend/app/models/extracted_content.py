from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid, utc_now

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.uploaded_file import UploadedFile


class ExtractedContent(Base):
    __tablename__ = "extracted_contents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id"),
        nullable=False,
    )
    uploaded_file_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("uploaded_files.id"),
        nullable=False,
    )
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    json_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    project: Mapped["Project"] = relationship(back_populates="extracted_contents")
    uploaded_file: Mapped["UploadedFile"] = relationship(
        back_populates="extracted_contents"
    )

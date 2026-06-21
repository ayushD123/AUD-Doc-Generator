from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid, utc_now

if TYPE_CHECKING:
    from app.models.project import Project


class OpenPoint(Base):
    __tablename__ = "open_points"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id"),
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Open")
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="raw_extracted",
    )
    refinement_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )
    raw_source_open_point_ids_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    source_file_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_content_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    project: Mapped["Project"] = relationship(back_populates="open_points")

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid, utc_now

if TYPE_CHECKING:
    from app.models.aud_plan import AUDPlan
    from app.models.extracted_content import ExtractedContent
    from app.models.job import Job
    from app.models.uploaded_file import UploadedFile


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    module_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
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

    uploaded_files: Mapped[list["UploadedFile"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    extracted_contents: Mapped[list["ExtractedContent"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    aud_plans: Mapped[list["AUDPlan"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

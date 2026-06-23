from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid, utc_now
from app.db.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.aud_generation_run import AUDGenerationRun
    from app.models.aud_plan import AUDPlan
    from app.models.aud_section_draft import AUDSectionDraft
    from app.models.evidence_item import EvidenceItem
    from app.models.extracted_content import ExtractedContent
    from app.models.generated_document import GeneratedDocument
    from app.models.job import Job
    from app.models.open_point import OpenPoint
    from app.models.section_evidence_pack import SectionEvidencePack
    from app.models.source_summary import SourceSummary
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
    open_points: Mapped[list["OpenPoint"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    generated_documents: Mapped[list["GeneratedDocument"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    evidence_items: Mapped[list["EvidenceItem"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    source_summaries: Mapped[list["SourceSummary"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    section_evidence_packs: Mapped[list["SectionEvidencePack"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    section_drafts: Mapped[list["AUDSectionDraft"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    aud_generation_runs: Mapped[list["AUDGenerationRun"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

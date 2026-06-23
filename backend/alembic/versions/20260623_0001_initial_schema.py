"""initial schema

Revision ID: 20260623_0001
Revises:
Create Date: 2026-06-23 00:01:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import oracle

revision: str = "20260623_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

utc_datetime = sa.DateTime(timezone=True).with_variant(
    oracle.TIMESTAMP(timezone=True),
    "oracle",
)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("email_id", sa.String(length=255), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("module_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", utc_datetime, nullable=False),
        sa.Column("updated_at", utc_datetime, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "aud_generation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("current_stage", sa.String(length=100), nullable=True),
        sa.Column("completed_stages_json", sa.Text(), nullable=False),
        sa.Column("warnings_json", sa.Text(), nullable=False),
        sa.Column("failed_stage", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("final_document_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", utc_datetime, nullable=True),
        sa.Column("completed_at", utc_datetime, nullable=True),
        sa.Column("created_at", utc_datetime, nullable=False),
        sa.Column("updated_at", utc_datetime, nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "aud_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("plan_json", sa.Text(), nullable=False),
        sa.Column("created_at", utc_datetime, nullable=False),
        sa.Column("updated_at", utc_datetime, nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "aud_section_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("section_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("draft_json", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(length=50), nullable=False),
        sa.Column("review_status", sa.String(length=50), nullable=False),
        sa.Column("created_at", utc_datetime, nullable=False),
        sa.Column("updated_at", utc_datetime, nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "generated_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("document_type", sa.String(length=100), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", utc_datetime, nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", utc_datetime, nullable=False),
        sa.Column("updated_at", utc_datetime, nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "open_points",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("topic", sa.String(length=500), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("refinement_status", sa.String(length=50), nullable=False),
        sa.Column("raw_source_open_point_ids_json", sa.Text(), nullable=True),
        sa.Column("source_file_id", sa.String(length=36), nullable=True),
        sa.Column("source_content_id", sa.String(length=36), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("created_at", utc_datetime, nullable=False),
        sa.Column("updated_at", utc_datetime, nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "section_evidence_packs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("section_id", sa.String(length=255), nullable=False),
        sa.Column("section_title", sa.String(length=500), nullable=False),
        sa.Column("pack_json", sa.Text(), nullable=False),
        sa.Column("created_at", utc_datetime, nullable=False),
        sa.Column("updated_at", utc_datetime, nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("file_type", sa.String(length=100), nullable=True),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("source_role", sa.String(length=100), nullable=True),
        sa.Column("created_at", utc_datetime, nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "extracted_contents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("uploaded_file_id", sa.String(length=36), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("json_content", sa.Text(), nullable=True),
        sa.Column("created_at", utc_datetime, nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["uploaded_file_id"], ["uploaded_files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "source_summaries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("source_uploaded_file_id", sa.String(length=36), nullable=True),
        sa.Column("source_role", sa.String(length=100), nullable=False),
        sa.Column("summary_type", sa.String(length=100), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=True),
        sa.Column("created_at", utc_datetime, nullable=False),
        sa.Column("updated_at", utc_datetime, nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["source_uploaded_file_id"], ["uploaded_files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "evidence_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("source_uploaded_file_id", sa.String(length=36), nullable=True),
        sa.Column("source_extracted_content_id", sa.String(length=36), nullable=True),
        sa.Column("evidence_type", sa.String(length=100), nullable=False),
        sa.Column("source_role", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("json_data", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.String(length=50), nullable=False),
        sa.Column("created_at", utc_datetime, nullable=False),
        sa.Column("updated_at", utc_datetime, nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["source_uploaded_file_id"], ["uploaded_files.id"]),
        sa.ForeignKeyConstraint(
            ["source_extracted_content_id"],
            ["extracted_contents.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("evidence_items")
    op.drop_table("source_summaries")
    op.drop_table("extracted_contents")
    op.drop_table("uploaded_files")
    op.drop_table("section_evidence_packs")
    op.drop_table("open_points")
    op.drop_table("jobs")
    op.drop_table("generated_documents")
    op.drop_table("aud_section_drafts")
    op.drop_table("aud_plans")
    op.drop_table("aud_generation_runs")
    op.drop_table("projects")

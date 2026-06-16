from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExtractedContent, UploadedFile
from app.schemas.source_priority import (
    SourceFileReference,
    SourcePriorityItem,
    SourcePriorityReport,
)

DEFAULT_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2] / "template" / "AUD_Editable_Template.docx"
)

SOURCE_ROLE_ORDER = [
    "template_aud",
    "fdd",
    "supporting_doc",
    "kt_ppt",
    "kt_transcript",
    "kt_session",
    "config_workbook",
    "final_aud_sample",
    "unknown",
]


def build_file_reference(
    uploaded_file: UploadedFile,
    extracted_content_by_file_id: dict[str, list[ExtractedContent]],
) -> SourceFileReference:
    extracted_contents = extracted_content_by_file_id.get(uploaded_file.id, [])

    return SourceFileReference(
        uploaded_file_id=uploaded_file.id,
        original_filename=uploaded_file.original_filename,
        source_role=uploaded_file.source_role or "unknown",
        file_type=uploaded_file.file_type,
        extracted_content_ids=[
            extracted_content.id for extracted_content in extracted_contents
        ],
    )


def build_priority_order(
    source_roles_present: set[str],
    has_explicit_template: bool,
) -> list[SourcePriorityItem]:
    priority_order: list[SourcePriorityItem] = []
    priority = 1

    if has_explicit_template:
        priority_order.append(
            SourcePriorityItem(
                source="template_aud",
                priority=priority,
                purpose="Controls AUD output structure and formatting.",
                rule="Use the explicitly uploaded template AUD.",
            )
        )
    else:
        priority_order.append(
            SourcePriorityItem(
                source="default_scm_template",
                priority=priority,
                purpose="Controls AUD output structure and formatting.",
                rule=(
                    "Use the default SCM AUD template because no explicit template "
                    "AUD is uploaded."
                ),
            )
        )
    priority += 1

    if "fdd" in source_roles_present:
        priority_order.append(
            SourcePriorityItem(
                source="fdd",
                priority=priority,
                purpose="Golden source for AUD content.",
                rule=(
                    "If FDD conflicts with KT transcript, PPT, or configuration "
                    "workbook, FDD wins."
                ),
            )
        )
        priority += 1

    for source, purpose, rule in [
        (
            "supporting_doc",
            "Primary project/customer document source.",
            "Use uploaded customer and project documents as primary content sources.",
        ),
        (
            "kt_ppt",
            "Topic flow and screenshot/image candidate source.",
            (
                "Use PPT content for flow and visual candidates, subordinate to FDD "
                "when FDD exists."
            ),
        ),
        (
            "kt_transcript",
            "Presenter emphasis, corrections, explanations, and screenshot relevance.",
            (
                "Override documents only when the presenter explicitly says a "
                "document is wrong, outdated, or should be ignored."
            ),
        ),
        (
            "kt_session",
            "Raw KT session source for later transcript/audio handling.",
            (
                "Use only after deterministic extraction or transcript processing "
                "makes content available."
            ),
        ),
        (
            "config_workbook",
            "Configuration validation and enrichment source.",
            "Validate and enrich details; do not copy workbook rows blindly into the AUD.",
        ),
        (
            "final_aud_sample",
            "Style and reference source.",
            "Use as style/reference only unless explicitly marked as template.",
        ),
        (
            "unknown",
            "Unclassified supporting input.",
            "Review before using because its business role is not explicit.",
        ),
    ]:
        if source in source_roles_present:
            priority_order.append(
                SourcePriorityItem(
                    source=source,
                    priority=priority,
                    purpose=purpose,
                    rule=rule,
                )
            )
            priority += 1

    return priority_order


def build_source_priority_report(
    session: Session,
    project_id: str,
) -> SourcePriorityReport:
    uploaded_files = list(
        session.scalars(
            select(UploadedFile)
            .where(UploadedFile.project_id == project_id)
            .order_by(UploadedFile.created_at.asc())
        ).all()
    )
    extracted_contents = list(
        session.scalars(
            select(ExtractedContent).where(ExtractedContent.project_id == project_id)
        ).all()
    )
    extracted_content_by_file_id: dict[str, list[ExtractedContent]] = {}

    for extracted_content in extracted_contents:
        extracted_content_by_file_id.setdefault(
            extracted_content.uploaded_file_id,
            [],
        ).append(extracted_content)

    source_roles_present = {
        uploaded_file.source_role or "unknown" for uploaded_file in uploaded_files
    }
    sorted_source_roles_present = [
        source_role
        for source_role in SOURCE_ROLE_ORDER
        if source_role in source_roles_present
    ]
    sorted_source_roles_present.extend(
        sorted(source_roles_present.difference(SOURCE_ROLE_ORDER))
    )

    has_explicit_template = "template_aud" in source_roles_present
    recommended_default_template_needed = not has_explicit_template
    golden_source_files = [
        build_file_reference(uploaded_file, extracted_content_by_file_id)
        for uploaded_file in uploaded_files
        if (uploaded_file.source_role or "unknown") == "fdd"
    ]
    warnings: list[str] = []
    notes: list[str] = []

    if not uploaded_files:
        warnings.append("No uploaded files are available for source prioritization.")

    if recommended_default_template_needed:
        notes.append(
            "No explicit template AUD is uploaded, so the default SCM AUD template "
            "should control structure and formatting."
        )

        if not DEFAULT_TEMPLATE_PATH.exists():
            warnings.append(
                "Default SCM AUD template file was not found under backend/template."
            )
    else:
        notes.append(
            "An explicit template AUD is uploaded, so it controls output structure and formatting."
        )

    if golden_source_files:
        notes.append(
            "FDD is present and is the golden source for content; FDD wins over "
            "PPT, transcript, and configuration workbook conflicts."
        )
    else:
        warnings.append(
            "No FDD uploaded; no golden content source is available yet."
        )

    if "config_workbook" in source_roles_present:
        notes.append(
            "Configuration workbook content should validate and enrich supported topics, not be copied blindly."
        )

    if "kt_transcript" in source_roles_present or "kt_session" in source_roles_present:
        notes.append(
            "KT transcript/session content should clarify presenter emphasis and override documents only for explicit corrections."
        )

    if (
        "final_aud_sample" in source_roles_present
        and "template_aud" not in source_roles_present
    ):
        notes.append(
            "Final AUD samples are style/reference only because none is marked as "
            "an explicit template."
        )

    notes.append(
        "Open Points should include unresolved questions only; unsupported sections "
        "should be omitted, left blank, or moved to Open Points based on context."
    )

    return SourcePriorityReport(
        has_explicit_template=has_explicit_template,
        golden_source_files=golden_source_files,
        source_roles_present=sorted_source_roles_present,
        priority_order=build_priority_order(
            source_roles_present=source_roles_present,
            has_explicit_template=has_explicit_template,
        ),
        warnings=warnings,
        recommended_default_template_needed=recommended_default_template_needed,
        notes=notes,
    )

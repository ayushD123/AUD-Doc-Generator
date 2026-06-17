import json
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AUDPlan, ExtractedContent, UploadedFile
from app.services.source_priority_service import build_source_priority_report

STANDARD_METADATA_TITLES = [
    "Cover Page",
    "Document Version History",
    "Table of Contents",
]
GENERIC_TRANSCRIPT_TITLES = [
    "Introduction",
    "Purpose and Scope",
    "Process Overview",
    "Key Design Considerations",
]
OPEN_POINTS_TITLE = "Open Points"
STANDARD_TITLES = {*STANDARD_METADATA_TITLES, OPEN_POINTS_TITLE}
LOW_VALUE_SLIDE_TITLES = {
    "agenda",
    "agenda only",
    "divider",
    "thank you",
    "thanks",
    "welcome",
}


@dataclass
class SectionCandidate:
    title: str
    source_file_ids: list[str] = field(default_factory=list)
    source_content_ids: list[str] = field(default_factory=list)
    source_role_basis: str = "unknown"
    confidence: str = "low"
    include_in_aud: bool = True
    notes: list[str] = field(default_factory=list)


def parse_json_content(extracted_content: ExtractedContent) -> dict[str, Any]:
    if not extracted_content.json_content:
        return {}

    try:
        parsed = json.loads(extracted_content.json_content)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def normalize_title(title: str) -> str:
    return " ".join(title.strip().split()).lower()


def is_low_value_slide_title(title: str) -> bool:
    normalized_title = normalize_title(title)

    if not normalized_title:
        return True

    if normalized_title in LOW_VALUE_SLIDE_TITLES:
        return True

    if normalized_title.startswith("agenda:"):
        return True

    return "kt session" in normalized_title or "knowledge transfer" in normalized_title


def slide_has_meaningful_content(slide: dict[str, Any]) -> bool:
    texts = slide.get("texts")
    if isinstance(texts, list) and any(
        isinstance(text, str) and text.strip() for text in texts
    ):
        return True

    tables = slide.get("tables")
    if isinstance(tables, list) and tables:
        return True

    image_count = slide.get("image_count")
    return isinstance(image_count, int) and image_count > 0


def make_section_id(index: int, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")
    return f"section-{index:03d}-{slug or 'untitled'}"


def add_candidate(
    candidates: list[SectionCandidate],
    seen_titles: set[str],
    candidate: SectionCandidate,
) -> None:
    normalized_title = normalize_title(candidate.title)

    if not normalized_title or normalized_title in seen_titles:
        return

    seen_titles.add(normalized_title)
    candidates.append(candidate)


def get_project_source_data(
    session: Session,
    project_id: str,
) -> tuple[list[ExtractedContent], dict[str, UploadedFile]]:
    uploaded_files = list(
        session.scalars(
            select(UploadedFile).where(UploadedFile.project_id == project_id)
        ).all()
    )
    extracted_contents = list(
        session.scalars(
            select(ExtractedContent)
            .where(ExtractedContent.project_id == project_id)
            .order_by(ExtractedContent.created_at.asc())
        ).all()
    )
    uploaded_file_by_id = {
        uploaded_file.id: uploaded_file for uploaded_file in uploaded_files
    }
    return extracted_contents, uploaded_file_by_id


def get_source_role(
    extracted_content: ExtractedContent,
    uploaded_file_by_id: dict[str, UploadedFile],
    json_content: dict[str, Any],
) -> str:
    uploaded_file = uploaded_file_by_id.get(extracted_content.uploaded_file_id)

    if uploaded_file and uploaded_file.source_role not in {None, "unknown"}:
        return uploaded_file.source_role

    source_role = json_content.get("source_role")
    if isinstance(source_role, str) and source_role != "unknown":
        return source_role

    if extracted_content.content_type == "pptx":
        return "kt_ppt"

    return "unknown"


def build_fdd_candidates(
    extracted_contents: list[ExtractedContent],
    uploaded_file_by_id: dict[str, UploadedFile],
) -> list[SectionCandidate]:
    candidates: list[SectionCandidate] = []
    seen_titles = {normalize_title(title) for title in STANDARD_TITLES}

    for extracted_content in extracted_contents:
        json_content = parse_json_content(extracted_content)
        source_role = get_source_role(
            extracted_content,
            uploaded_file_by_id,
            json_content,
        )

        if source_role != "fdd":
            continue

        headings = json_content.get("headings")
        if not isinstance(headings, list):
            continue

        for heading in headings:
            if not isinstance(heading, dict):
                continue

            title = heading.get("text")
            if not isinstance(title, str):
                continue

            add_candidate(
                candidates,
                seen_titles,
                SectionCandidate(
                    title=title,
                    source_file_ids=[extracted_content.uploaded_file_id],
                    source_content_ids=[extracted_content.id],
                    source_role_basis="fdd",
                    confidence="high",
                    notes=["Derived from FDD heading."],
                ),
            )

    return candidates


def has_extracted_content_for_role(
    extracted_contents: list[ExtractedContent],
    uploaded_file_by_id: dict[str, UploadedFile],
    target_source_role: str,
) -> bool:
    for extracted_content in extracted_contents:
        json_content = parse_json_content(extracted_content)
        source_role = get_source_role(
            extracted_content,
            uploaded_file_by_id,
            json_content,
        )

        if source_role == target_source_role:
            return True

    return False


def build_ppt_candidates(
    extracted_contents: list[ExtractedContent],
    uploaded_file_by_id: dict[str, UploadedFile],
) -> list[SectionCandidate]:
    candidates: list[SectionCandidate] = []
    seen_titles = {normalize_title(title) for title in STANDARD_TITLES}

    for extracted_content in extracted_contents:
        json_content = parse_json_content(extracted_content)
        source_role = get_source_role(
            extracted_content,
            uploaded_file_by_id,
            json_content,
        )

        if source_role != "kt_ppt":
            continue

        slides = json_content.get("slides")
        if not isinstance(slides, list):
            continue

        for slide in slides:
            if not isinstance(slide, dict):
                continue

            title = slide.get("title")
            if not isinstance(title, str) or is_low_value_slide_title(title):
                continue

            if not slide_has_meaningful_content(slide):
                continue

            slide_number = slide.get("slide_number")
            notes = ["Derived from meaningful PPT slide title."]
            if isinstance(slide_number, int):
                notes.append(f"Source slide {slide_number}.")

            add_candidate(
                candidates,
                seen_titles,
                SectionCandidate(
                    title=title,
                    source_file_ids=[extracted_content.uploaded_file_id],
                    source_content_ids=[extracted_content.id],
                    source_role_basis="kt_ppt",
                    confidence="medium",
                    notes=notes,
                ),
            )

    return candidates


def build_transcript_candidates(
    extracted_contents: list[ExtractedContent],
    uploaded_file_by_id: dict[str, UploadedFile],
) -> list[SectionCandidate]:
    transcript_content_ids: list[str] = []
    transcript_file_ids: list[str] = []

    for extracted_content in extracted_contents:
        json_content = parse_json_content(extracted_content)
        source_role = get_source_role(
            extracted_content,
            uploaded_file_by_id,
            json_content,
        )

        if extracted_content.content_type == "transcript" or source_role in {
            "kt_transcript",
            "kt_session",
        }:
            transcript_content_ids.append(extracted_content.id)
            transcript_file_ids.append(extracted_content.uploaded_file_id)

    if not transcript_content_ids:
        return []

    return [
        SectionCandidate(
            title=title,
            source_file_ids=sorted(set(transcript_file_ids)),
            source_content_ids=sorted(set(transcript_content_ids)),
            source_role_basis="kt_transcript",
            confidence="low",
            notes=["Generic default section because no FDD or PPT structure exists."],
        )
        for title in GENERIC_TRANSCRIPT_TITLES
    ]


def build_standard_sections(default_template_required: bool) -> list[SectionCandidate]:
    template_note = (
        "Default SCM template required because no explicit template AUD is uploaded."
        if default_template_required
        else "Explicit template AUD is available."
    )
    standard_sections = [
        SectionCandidate(
            title=title,
            source_role_basis="aud_template",
            confidence="high",
            notes=["Standard AUD metadata section.", template_note],
        )
        for title in STANDARD_METADATA_TITLES
    ]
    standard_sections.append(
        SectionCandidate(
            title=OPEN_POINTS_TITLE,
            source_role_basis="aud_template",
            confidence="medium",
            notes=["Include unresolved questions only."],
        )
    )
    return standard_sections


def render_sections(candidates: list[SectionCandidate]) -> list[dict[str, Any]]:
    return [
        {
            "section_id": make_section_id(index, candidate.title),
            "title": candidate.title,
            "source_file_ids": candidate.source_file_ids,
            "source_content_ids": candidate.source_content_ids,
            "source_role_basis": candidate.source_role_basis,
            "confidence": candidate.confidence,
            "include_in_aud": candidate.include_in_aud,
            "notes": candidate.notes,
        }
        for index, candidate in enumerate(candidates, start=1)
    ]


def build_aud_plan_payload(session: Session, project_id: str) -> dict[str, Any]:
    source_priority_report = build_source_priority_report(session, project_id)
    extracted_contents, uploaded_file_by_id = get_project_source_data(
        session,
        project_id,
    )
    default_template_required = (
        source_priority_report.recommended_default_template_needed
    )
    fdd_candidates = build_fdd_candidates(extracted_contents, uploaded_file_by_id)
    has_fdd_extracted_content = has_extracted_content_for_role(
        extracted_contents,
        uploaded_file_by_id,
        "fdd",
    )
    has_ppt_extracted_content = has_extracted_content_for_role(
        extracted_contents,
        uploaded_file_by_id,
        "kt_ppt",
    )

    if has_fdd_extracted_content:
        generation_basis = "fdd_headings"
        content_candidates = fdd_candidates
    elif has_ppt_extracted_content:
        ppt_candidates = build_ppt_candidates(extracted_contents, uploaded_file_by_id)
        generation_basis = "ppt_slide_titles"
        content_candidates = ppt_candidates
    else:
        transcript_candidates = build_transcript_candidates(
            extracted_contents,
            uploaded_file_by_id,
        )
        generation_basis = (
            "transcript_generic_sections"
            if transcript_candidates
            else "standard_sections_only"
        )
        content_candidates = transcript_candidates

    standard_sections = build_standard_sections(default_template_required)
    sections = [
        *standard_sections[: len(STANDARD_METADATA_TITLES)],
        *content_candidates,
        standard_sections[-1],
    ]

    return {
        "project_id": project_id,
        "status": "draft",
        "generation_basis": generation_basis,
        "default_template_required": default_template_required,
        "source_priority": source_priority_report.model_dump(),
        "sections": render_sections(sections),
    }


def generate_aud_plan(session: Session, project_id: str) -> AUDPlan:
    plan_payload = build_aud_plan_payload(session, project_id)
    aud_plan = AUDPlan(
        project_id=project_id,
        status="draft",
        plan_json=json.dumps(plan_payload, indent=2),
    )
    session.add(aud_plan)
    session.commit()
    session.refresh(aud_plan)
    return aud_plan

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EvidenceItem, ExtractedContent, UploadedFile


FDD_PRIORITY = 100
CONFIG_PRIORITY = 60
PPT_PRIORITY = 70
TRANSCRIPT_PRIORITY = 80
FINAL_AUD_SAMPLE_PRIORITY = 30
DEFAULT_PRIORITY = 50


@dataclass
class EvidenceCandidate:
    project_id: str
    source_uploaded_file_id: str | None
    source_extracted_content_id: str | None
    evidence_type: str
    source_role: str | None
    title: str | None
    text: str | None
    priority: int
    confidence: str = "medium"
    json_data: dict[str, Any] = field(default_factory=dict)


def parse_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def compact_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def evidence_priority(source_role: str | None, content_type: str | None = None) -> int:
    if source_role == "fdd":
        return FDD_PRIORITY
    if source_role == "config_workbook":
        return CONFIG_PRIORITY
    if source_role == "kt_ppt":
        return PPT_PRIORITY
    if source_role in {"kt_transcript", "kt_session"}:
        return TRANSCRIPT_PRIORITY
    if source_role == "final_aud_sample":
        return FINAL_AUD_SAMPLE_PRIORITY
    if content_type == "oci_document_understanding":
        return document_ai_priority(source_role)
    return DEFAULT_PRIORITY


def document_ai_priority(source_role: str | None) -> int:
    if source_role == "fdd":
        return 95
    if source_role == "supporting_doc":
        return 65
    return 50


def get_source_role(
    extracted_content: ExtractedContent,
    uploaded_file: UploadedFile | None,
    json_content: dict[str, Any],
) -> str | None:
    if uploaded_file and uploaded_file.source_role:
        return uploaded_file.source_role

    source_role = json_content.get("source_role")
    return source_role if isinstance(source_role, str) else None


def with_style_reference(
    source_role: str | None,
    json_data: dict[str, Any],
) -> dict[str, Any]:
    if source_role == "final_aud_sample":
        return {**json_data, "style_reference": True}

    return json_data


def table_text(rows: Any) -> str:
    if not isinstance(rows, list):
        return ""

    rendered_rows = []
    for row in rows:
        if isinstance(row, list):
            rendered_rows.append(" | ".join(compact_text(value) for value in row))
    return "\n".join(row for row in rendered_rows if row.strip())


def chunk_text(text: str | None, max_characters: int = 1200) -> list[str]:
    paragraphs = [
        paragraph.strip()
        for paragraph in (text or "").splitlines()
        if paragraph.strip()
    ]
    chunks: list[str] = []
    current: list[str] = []
    current_count = 0

    for paragraph in paragraphs:
        if paragraph.startswith("[Heading:") and paragraph.endswith("]"):
            continue

        next_count = current_count + len(paragraph) + 2
        if current and next_count > max_characters:
            chunks.append("\n".join(current))
            current = []
            current_count = 0

        current.append(paragraph)
        current_count += len(paragraph) + 2

    if current:
        chunks.append("\n".join(current))

    return chunks


def iter_docx_evidence(
    extracted_content: ExtractedContent,
    uploaded_file: UploadedFile | None,
    json_content: dict[str, Any],
    source_role: str | None,
) -> list[EvidenceCandidate]:
    priority = evidence_priority(source_role, extracted_content.content_type)
    candidates: list[EvidenceCandidate] = []

    for heading in json_content.get("headings", []):
        if not isinstance(heading, dict):
            continue
        title = compact_text(heading.get("text"))
        if title:
            candidates.append(
                EvidenceCandidate(
                    project_id=extracted_content.project_id,
                    source_uploaded_file_id=extracted_content.uploaded_file_id,
                    source_extracted_content_id=extracted_content.id,
                    evidence_type="heading",
                    source_role=source_role,
                    title=title,
                    text=title,
                    priority=priority,
                    confidence="high" if source_role == "fdd" else "medium",
                    json_data=with_style_reference(source_role, {"heading": heading}),
                )
            )

    for index, paragraph in enumerate(chunk_text(extracted_content.text_content), start=1):
        candidates.append(
            EvidenceCandidate(
                project_id=extracted_content.project_id,
                source_uploaded_file_id=extracted_content.uploaded_file_id,
                source_extracted_content_id=extracted_content.id,
                evidence_type="paragraph",
                source_role=source_role,
                title=f"{extracted_content.title or 'Document'} paragraph {index}",
                text=paragraph,
                priority=priority,
                confidence="high" if source_role == "fdd" else "medium",
                json_data=with_style_reference(source_role, {"chunk_index": index}),
            )
        )

    for table in json_content.get("tables", []):
        if not isinstance(table, dict):
            continue
        rows = table.get("rows")
        candidates.append(
            EvidenceCandidate(
                project_id=extracted_content.project_id,
                source_uploaded_file_id=extracted_content.uploaded_file_id,
                source_extracted_content_id=extracted_content.id,
                evidence_type="table",
                source_role=source_role,
                title=f"{extracted_content.title or 'Document'} table {table.get('index')}",
                text=table_text(rows),
                priority=priority,
                confidence="high" if source_role == "fdd" else "medium",
                json_data=with_style_reference(source_role, {"table": table}),
            )
        )

    for comment in json_content.get("comments", []):
        if not isinstance(comment, dict):
            continue
        text = compact_text(comment.get("text"))
        if text:
            candidates.append(
                EvidenceCandidate(
                    project_id=extracted_content.project_id,
                    source_uploaded_file_id=extracted_content.uploaded_file_id,
                    source_extracted_content_id=extracted_content.id,
                    evidence_type="open_item",
                    source_role=source_role,
                    title="Document comment",
                    text=text,
                    priority=priority,
                    confidence="high" if source_role == "fdd" else "medium",
                    json_data=with_style_reference(source_role, {"comment": comment}),
                )
            )

    return candidates


def iter_spreadsheet_evidence(
    extracted_content: ExtractedContent,
    json_content: dict[str, Any],
    source_role: str | None,
) -> list[EvidenceCandidate]:
    candidates: list[EvidenceCandidate] = []
    priority = CONFIG_PRIORITY if source_role == "config_workbook" else evidence_priority(source_role)

    for sheet in json_content.get("sheets", []):
        if not isinstance(sheet, dict):
            continue

        title = compact_text(sheet.get("name")) or "Workbook sheet"
        rows = sheet.get("rows") if isinstance(sheet.get("rows"), list) else []
        summary = (
            f"Sheet {title}: {sheet.get('non_empty_row_count', len(rows))} "
            f"non-empty row(s), {sheet.get('max_column', 0)} column(s)."
        )
        candidates.append(
            EvidenceCandidate(
                project_id=extracted_content.project_id,
                source_uploaded_file_id=extracted_content.uploaded_file_id,
                source_extracted_content_id=extracted_content.id,
                evidence_type="workbook_sheet",
                source_role=source_role,
                title=title,
                text=summary,
                priority=priority,
                json_data={"sheet": sheet},
            )
        )

        if rows:
            candidates.append(
                EvidenceCandidate(
                    project_id=extracted_content.project_id,
                    source_uploaded_file_id=extracted_content.uploaded_file_id,
                    source_extracted_content_id=extracted_content.id,
                    evidence_type="workbook_table",
                    source_role=source_role,
                    title=f"{title} table",
                    text="\n".join(
                        " | ".join(compact_text(value) for value in row.get("values", []))
                        for row in rows
                        if isinstance(row, dict)
                    ),
                    priority=priority,
                    json_data={"sheet_name": title, "rows": rows},
                )
            )

    return candidates


def iter_ppt_evidence(
    extracted_content: ExtractedContent,
    json_content: dict[str, Any],
    source_role: str | None,
) -> list[EvidenceCandidate]:
    candidates: list[EvidenceCandidate] = []
    priority = PPT_PRIORITY if source_role == "kt_ppt" else evidence_priority(source_role)

    for slide in json_content.get("slides", []):
        if not isinstance(slide, dict):
            continue
        slide_number = slide.get("slide_number") or slide.get("index")
        title = compact_text(slide.get("title")) or f"Slide {slide_number}"
        text_parts = [title]
        text_parts.extend(compact_text(value) for value in slide.get("texts", []) if value)
        for table in slide.get("tables", []):
            if isinstance(table, dict):
                text_parts.append(table_text(table.get("rows")))
        candidates.append(
            EvidenceCandidate(
                project_id=extracted_content.project_id,
                source_uploaded_file_id=extracted_content.uploaded_file_id,
                source_extracted_content_id=extracted_content.id,
                evidence_type="slide",
                source_role=source_role,
                title=title,
                text="\n".join(part for part in text_parts if part),
                priority=priority,
                json_data={"slide": slide},
            )
        )

        for image_path in slide.get("image_paths", []):
            candidates.append(
                EvidenceCandidate(
                    project_id=extracted_content.project_id,
                    source_uploaded_file_id=extracted_content.uploaded_file_id,
                    source_extracted_content_id=extracted_content.id,
                    evidence_type="image_reference",
                    source_role=source_role,
                    title=f"{title} image",
                    text=compact_text(image_path),
                    priority=priority,
                    json_data={"slide_number": slide_number, "image_path": image_path},
                )
            )

    return candidates


def iter_transcript_evidence(
    extracted_content: ExtractedContent,
    source_role: str | None,
) -> list[EvidenceCandidate]:
    priority = TRANSCRIPT_PRIORITY if source_role in {"kt_transcript", "kt_session"} else evidence_priority(source_role)
    return [
        EvidenceCandidate(
            project_id=extracted_content.project_id,
            source_uploaded_file_id=extracted_content.uploaded_file_id,
            source_extracted_content_id=extracted_content.id,
            evidence_type="transcript_segment",
            source_role=source_role,
            title=f"{extracted_content.title or 'Transcript'} segment {index}",
            text=chunk,
            priority=priority,
            json_data={"segment_index": index},
        )
        for index, chunk in enumerate(chunk_text(extracted_content.text_content), start=1)
    ]


def iter_document_ai_evidence(
    extracted_content: ExtractedContent,
    json_content: dict[str, Any],
    source_role: str | None,
) -> list[EvidenceCandidate]:
    priority = document_ai_priority(source_role)
    candidates: list[EvidenceCandidate] = []

    for index, page in enumerate(json_content.get("pages", []), start=1):
        if not isinstance(page, dict):
            continue
        page_text = compact_text(page.get("text"))
        if page_text:
            candidates.append(
                EvidenceCandidate(
                    project_id=extracted_content.project_id,
                    source_uploaded_file_id=extracted_content.uploaded_file_id,
                    source_extracted_content_id=extracted_content.id,
                    evidence_type="paragraph",
                    source_role=source_role,
                    title=f"{extracted_content.title or 'OCR'} page {page.get('page_number', index)}",
                    text=page_text,
                    priority=priority,
                    json_data={"provider": "oci_document_understanding", "page": page},
                )
            )

    for table in json_content.get("tables", []):
        if not isinstance(table, dict):
            continue
        candidates.append(
            EvidenceCandidate(
                project_id=extracted_content.project_id,
                source_uploaded_file_id=extracted_content.uploaded_file_id,
                source_extracted_content_id=extracted_content.id,
                evidence_type="document_ai_table",
                source_role=source_role,
                title=f"{extracted_content.title or 'Document AI'} table {table.get('index')}",
                text=table_text(table.get("rows")),
                priority=priority,
                json_data={"provider": "oci_document_understanding", "table": table},
            )
        )

    return candidates


def evidence_candidates_for_content(
    extracted_content: ExtractedContent,
    uploaded_file: UploadedFile | None,
) -> list[EvidenceCandidate]:
    json_content = parse_json_object(extracted_content.json_content)
    source_role = get_source_role(extracted_content, uploaded_file, json_content)

    if extracted_content.content_type == "docx":
        return iter_docx_evidence(extracted_content, uploaded_file, json_content, source_role)
    if extracted_content.content_type == "spreadsheet":
        return iter_spreadsheet_evidence(extracted_content, json_content, source_role)
    if extracted_content.content_type == "pptx":
        return iter_ppt_evidence(extracted_content, json_content, source_role)
    if extracted_content.content_type == "transcript":
        return iter_transcript_evidence(extracted_content, source_role)
    if extracted_content.content_type == "oci_document_understanding":
        return iter_document_ai_evidence(extracted_content, json_content, source_role)

    if source_role == "final_aud_sample":
        return [
            EvidenceCandidate(
                project_id=extracted_content.project_id,
                source_uploaded_file_id=extracted_content.uploaded_file_id,
                source_extracted_content_id=extracted_content.id,
                evidence_type="paragraph",
                source_role=source_role,
                title=extracted_content.title,
                text=chunk,
                priority=FINAL_AUD_SAMPLE_PRIORITY,
                json_data={"style_reference": True, "chunk_index": index},
            )
            for index, chunk in enumerate(chunk_text(extracted_content.text_content), start=1)
        ]

    return []


def deterministic_key(candidate: EvidenceCandidate) -> str:
    text_hash = hashlib.sha256((candidate.text or "").encode("utf-8")).hexdigest()[:16]
    return "|".join(
        [
            candidate.project_id,
            candidate.source_extracted_content_id or "",
            candidate.evidence_type,
            candidate.title or "",
            text_hash,
        ]
    )


def existing_evidence_keys(session: Session, project_id: str) -> set[str]:
    keys: set[str] = set()
    evidence_items = session.scalars(
        select(EvidenceItem).where(EvidenceItem.project_id == project_id)
    )

    for item in evidence_items:
        json_data = parse_json_object(item.json_data)
        key = json_data.get("deterministic_key")
        if isinstance(key, str):
            keys.add(key)
            continue

        keys.add(
            deterministic_key(
                EvidenceCandidate(
                    project_id=item.project_id,
                    source_uploaded_file_id=item.source_uploaded_file_id,
                    source_extracted_content_id=item.source_extracted_content_id,
                    evidence_type=item.evidence_type,
                    source_role=item.source_role,
                    title=item.title,
                    text=item.text,
                    priority=item.priority,
                    confidence=item.confidence,
                )
            )
        )

    return keys


def add_evidence_candidate(
    session: Session,
    candidate: EvidenceCandidate,
    seen_keys: set[str],
) -> bool:
    key = deterministic_key(candidate)
    if key in seen_keys:
        return False

    json_payload = {**candidate.json_data, "deterministic_key": key}
    session.add(
        EvidenceItem(
            project_id=candidate.project_id,
            source_uploaded_file_id=candidate.source_uploaded_file_id,
            source_extracted_content_id=candidate.source_extracted_content_id,
            evidence_type=candidate.evidence_type,
            source_role=candidate.source_role,
            title=candidate.title,
            text=candidate.text,
            json_data=json.dumps(json_payload),
            priority=candidate.priority,
            confidence=candidate.confidence,
        )
    )
    seen_keys.add(key)
    return True


def build_evidence_index(session: Session, project_id: str) -> list[EvidenceItem]:
    extracted_contents = list(
        session.scalars(
            select(ExtractedContent)
            .where(ExtractedContent.project_id == project_id)
            .order_by(ExtractedContent.created_at.asc())
        )
    )
    seen_keys = existing_evidence_keys(session, project_id)

    for extracted_content in extracted_contents:
        uploaded_file = session.get(UploadedFile, extracted_content.uploaded_file_id)
        for candidate in evidence_candidates_for_content(extracted_content, uploaded_file):
            add_evidence_candidate(session, candidate, seen_keys)

    session.commit()
    return list(
        session.scalars(
            select(EvidenceItem)
            .where(EvidenceItem.project_id == project_id)
            .order_by(EvidenceItem.priority.desc(), EvidenceItem.created_at.asc())
        )
    )

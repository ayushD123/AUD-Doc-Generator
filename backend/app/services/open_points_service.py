import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import ExtractedContent, OpenPoint, UploadedFile

OPEN_ITEM_INDICATORS = [
    "needs more discussion",
    "to be confirmed",
    "tbd",
    "pending",
    "awaiting confirmation",
    "open item",
    "confirm with",
    "another session",
    "not finalized",
    "will be confirmed",
]
EXPLICIT_OPEN_SECTION_TITLES = [
    "Open Items",
    "Open Points",
    "Open and Close Issues",
    "Gaps and Resolutions",
]
RESOLVED_STATUS_VALUES = {
    "aligned",
    "closed",
    "done",
    "resolved",
}
CONFLICT_INDICATORS = [
    "conflict",
    "contradict",
    "contradiction",
    "does not match",
    "mismatch",
]
TEXT_SPLIT_PATTERN = re.compile(r"[\r\n]+|(?<=[.!?])\s+")


@dataclass
class OpenPointCandidate:
    topic: str
    question: str
    source_file_id: str | None
    source_content_id: str | None
    evidence: str | None
    source_role: str


def parse_json_content(extracted_content: ExtractedContent) -> dict[str, Any]:
    if not extracted_content.json_content:
        return {}

    try:
        parsed = json.loads(extracted_content.json_content)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_key(value: str) -> str:
    return normalize_text(value).lower()


def sentence_contains_any(sentence: str, indicators: list[str]) -> bool:
    normalized_sentence = sentence.lower()
    return any(indicator in normalized_sentence for indicator in indicators)


def has_resolved_status(value: str) -> bool:
    normalized_value = normalize_key(value)
    status_match = re.search(r"\bstatus\s*[:=-]\s*([a-z ]+)", normalized_value)

    if status_match:
        status_value = status_match.group(1).strip()
        return any(status_value.startswith(status) for status in RESOLVED_STATUS_VALUES)

    return any(
        re.search(rf"\b{re.escape(status)}\b", normalized_value)
        for status in RESOLVED_STATUS_VALUES
    )


def is_open_item_text(value: str) -> bool:
    return sentence_contains_any(value, OPEN_ITEM_INDICATORS)


def split_text_candidates(text_content: str | None) -> list[str]:
    if not text_content:
        return []

    return [
        normalize_text(part)
        for part in TEXT_SPLIT_PATTERN.split(text_content)
        if normalize_text(part)
    ]


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

    if uploaded_file and uploaded_file.source_role:
        return uploaded_file.source_role

    source_role = json_content.get("source_role")
    return source_role if isinstance(source_role, str) else "unknown"


def make_candidate(
    extracted_content: ExtractedContent,
    source_role: str,
    text: str,
    topic: str,
    evidence: str | None = None,
) -> OpenPointCandidate:
    normalized_text = normalize_text(text)
    return OpenPointCandidate(
        topic=topic,
        question=normalized_text,
        source_file_id=extracted_content.uploaded_file_id,
        source_content_id=extracted_content.id,
        evidence=evidence or normalized_text,
        source_role=source_role,
    )


def extract_comment_candidates(
    extracted_content: ExtractedContent,
    source_role: str,
    json_content: dict[str, Any],
) -> list[OpenPointCandidate]:
    comments = json_content.get("comments")
    candidates: list[OpenPointCandidate] = []

    if not isinstance(comments, list):
        return candidates

    for comment in comments:
        if not isinstance(comment, dict):
            continue

        text = comment.get("text")
        if not isinstance(text, str):
            continue

        if has_resolved_status(text) or not is_open_item_text(text):
            continue

        candidates.append(
            make_candidate(
                extracted_content=extracted_content,
                source_role=source_role,
                text=text,
                topic="FDD Comment" if source_role == "fdd" else "Comment",
            )
        )

    return candidates


def iter_table_rows(json_content: dict[str, Any]) -> list[str]:
    rendered_rows: list[str] = []

    for table in json_content.get("tables", []):
        if not isinstance(table, dict):
            continue

        rows = table.get("rows")
        if not isinstance(rows, list):
            continue

        for row in rows:
            if isinstance(row, list):
                rendered_rows.append(" | ".join(str(cell or "") for cell in row))

    for sheet in json_content.get("sheets", []):
        if not isinstance(sheet, dict):
            continue

        rows = sheet.get("rows")
        if not isinstance(rows, list):
            continue

        for row in rows:
            if isinstance(row, dict):
                values = row.get("values")
                if isinstance(values, list):
                    rendered_rows.append(" | ".join(str(cell or "") for cell in values))

    return rendered_rows


def extract_json_row_candidates(
    extracted_content: ExtractedContent,
    source_role: str,
    json_content: dict[str, Any],
) -> list[OpenPointCandidate]:
    candidates: list[OpenPointCandidate] = []

    for row_text in iter_table_rows(json_content):
        if has_resolved_status(row_text) or not is_open_item_text(row_text):
            continue

        candidates.append(
            make_candidate(
                extracted_content=extracted_content,
                source_role=source_role,
                text=row_text,
                topic="Open Item",
            )
        )

    return candidates


def extract_text_candidates(
    extracted_content: ExtractedContent,
    source_role: str,
) -> list[OpenPointCandidate]:
    candidates: list[OpenPointCandidate] = []

    for sentence in split_text_candidates(extracted_content.text_content):
        if has_resolved_status(sentence) or not is_open_item_text(sentence):
            continue

        candidates.append(
            make_candidate(
                extracted_content=extracted_content,
                source_role=source_role,
                text=sentence,
                topic="Open Item",
            )
        )

    return candidates


def extract_explicit_section_candidates(
    extracted_content: ExtractedContent,
    source_role: str,
) -> list[OpenPointCandidate]:
    lines = [
        normalize_text(line)
        for line in (extracted_content.text_content or "").splitlines()
        if normalize_text(line)
    ]
    candidates: list[OpenPointCandidate] = []

    for index, line in enumerate(lines):
        section_title = next(
            (
                title
                for title in EXPLICIT_OPEN_SECTION_TITLES
                if normalize_key(line).strip("[]:") == normalize_key(title)
                or normalize_key(title) in normalize_key(line)
            ),
            None,
        )

        if not section_title:
            continue

        for next_line in lines[index + 1 : index + 6]:
            if normalize_key(next_line) in {
                normalize_key(title) for title in EXPLICIT_OPEN_SECTION_TITLES
            }:
                continue

            if has_resolved_status(next_line):
                continue

            if is_open_item_text(next_line) or "?" in next_line:
                candidates.append(
                    make_candidate(
                        extracted_content=extracted_content,
                        source_role=source_role,
                        text=next_line,
                        topic=section_title,
                    )
                )

    return candidates


def is_non_fdd_conflict(candidate: OpenPointCandidate) -> bool:
    if candidate.source_role == "fdd":
        return False

    haystack = f"{candidate.question} {candidate.evidence or ''}".lower()
    return any(indicator in haystack for indicator in CONFLICT_INDICATORS)


def dedupe_candidates(candidates: list[OpenPointCandidate]) -> list[OpenPointCandidate]:
    deduped: list[OpenPointCandidate] = []
    seen: set[str] = set()

    for candidate in candidates:
        key = normalize_key(candidate.question)
        if not key or key in seen:
            continue

        seen.add(key)
        deduped.append(candidate)

    return deduped


def extract_open_point_candidates(
    extracted_contents: list[ExtractedContent],
    uploaded_file_by_id: dict[str, UploadedFile],
) -> list[OpenPointCandidate]:
    candidates: list[OpenPointCandidate] = []
    fdd_has_clear_content = False

    for extracted_content in extracted_contents:
        json_content = parse_json_content(extracted_content)
        source_role = get_source_role(
            extracted_content,
            uploaded_file_by_id,
            json_content,
        )

        if source_role == "fdd" and normalize_text(extracted_content.text_content or ""):
            fdd_has_clear_content = True

        candidates.extend(
            extract_comment_candidates(extracted_content, source_role, json_content)
        )
        candidates.extend(
            extract_json_row_candidates(extracted_content, source_role, json_content)
        )
        candidates.extend(extract_text_candidates(extracted_content, source_role))
        candidates.extend(
            extract_explicit_section_candidates(extracted_content, source_role)
        )

    if fdd_has_clear_content:
        candidates = [
            candidate for candidate in candidates if not is_non_fdd_conflict(candidate)
        ]

    return dedupe_candidates(candidates)


def extract_open_points(session: Session, project_id: str) -> list[OpenPoint]:
    extracted_contents, uploaded_file_by_id = get_project_source_data(
        session,
        project_id,
    )
    candidates = extract_open_point_candidates(
        extracted_contents,
        uploaded_file_by_id,
    )

    session.execute(delete(OpenPoint).where(OpenPoint.project_id == project_id))

    open_points = [
        OpenPoint(
            project_id=project_id,
            topic=candidate.topic,
            question=candidate.question,
            status="Open",
            source_file_id=candidate.source_file_id,
            source_content_id=candidate.source_content_id,
            evidence=candidate.evidence,
        )
        for candidate in candidates
    ]
    session.add_all(open_points)
    session.commit()

    for open_point in open_points:
        session.refresh(open_point)

    return open_points

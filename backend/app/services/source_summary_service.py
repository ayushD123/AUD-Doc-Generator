from __future__ import annotations

import json
from dataclasses import dataclass
from traceback import format_exception_only

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import EvidenceItem, SourceSummary
from app.services.llm import LLMConfigurationError, LLMService, build_llm_service
from app.services.llm.base import get_prompt_body_budget

SOURCE_SUMMARY_SCHEMA_KEYS = {
    "source_role",
    "summary",
    "important_topics",
    "tables_or_configurations",
    "processes",
    "screenshots_or_images_to_consider",
    "open_or_unresolved_items",
    "source_confidence",
    "aud_usage_guidance",
}

LIST_FIELDS = {
    "important_topics",
    "tables_or_configurations",
    "processes",
    "screenshots_or_images_to_consider",
    "open_or_unresolved_items",
}

ROLE_SUMMARY_TYPES = {
    "fdd": "fdd_summary",
    "kt_ppt": "ppt_summary",
    "kt_session": "transcript_summary",
    "kt_transcript": "transcript_summary",
    "config_workbook": "config_summary",
    "final_aud_sample": "style_reference_summary",
}

EVIDENCE_PREVIEW_CHAR_LIMIT = 1200


@dataclass(frozen=True)
class EvidenceSourceGroup:
    source_uploaded_file_id: str | None
    source_role: str
    evidence_items: list[EvidenceItem]


@dataclass(frozen=True)
class SourceSummaryGenerationResult:
    summaries: list[SourceSummary]
    warnings: list[str]


def get_summary_type(source_role: str) -> str:
    if source_role == "oci_document_understanding":
        return "document_ai_summary"

    return ROLE_SUMMARY_TYPES.get(source_role, "document_ai_summary")


def normalize_summary_payload(payload: dict, source_role: str) -> dict:
    normalized = dict(payload)

    for key in SOURCE_SUMMARY_SCHEMA_KEYS:
        normalized.setdefault(key, [] if key in LIST_FIELDS else "")

    normalized["source_role"] = str(normalized.get("source_role") or source_role)

    for key in LIST_FIELDS:
        value = normalized.get(key)

        if value is None:
            normalized[key] = []
        elif not isinstance(value, list):
            normalized[key] = [str(value)]

    if normalized["source_confidence"] not in {"high", "medium", "low"}:
        normalized["source_confidence"] = "medium"

    return {key: normalized[key] for key in SOURCE_SUMMARY_SCHEMA_KEYS}


def group_evidence_items(evidence_items: list[EvidenceItem]) -> list[EvidenceSourceGroup]:
    grouped: dict[tuple[str | None, str], list[EvidenceItem]] = {}

    for item in evidence_items:
        source_role = item.source_role or "unknown"
        key = (item.source_uploaded_file_id, source_role)
        grouped.setdefault(key, []).append(item)

    groups = [
        EvidenceSourceGroup(
            source_uploaded_file_id=source_uploaded_file_id,
            source_role=source_role,
            evidence_items=items,
        )
        for (source_uploaded_file_id, source_role), items in grouped.items()
    ]
    return sorted(
        groups,
        key=lambda group: (
            group.source_role,
            group.source_uploaded_file_id or "",
        ),
    )


def build_source_summary_prompt(
    group: EvidenceSourceGroup,
    settings: Settings | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    role_instruction = get_source_role_instruction(group.source_role)
    prompt_budget = get_prompt_body_budget(resolved_settings.OCI_GENAI_MAX_INPUT_CHARS)
    evidence_block = build_bounded_evidence_block(
        group.evidence_items,
        max_chars=max(2000, prompt_budget - 6000),
    )

    prompt = f"""
Create a concise source summary for AUD preparation.

Rules:
- Use only the provided evidence.
- Do not invent missing details.
- Mark missing, unclear, or unsupported information explicitly.
- Keep the summary concise and suitable for later AUD planning.
- Preserve source meaning and do not overstate confidence.

Source role: {group.source_role}
Source uploaded file id: {group.source_uploaded_file_id or "not available"}

Role-specific instruction:
{role_instruction}

Return strict JSON only with this exact object shape:
{{
  "source_role": "{group.source_role}",
  "summary": "...",
  "important_topics": [],
  "tables_or_configurations": [],
  "processes": [],
  "screenshots_or_images_to_consider": [],
  "open_or_unresolved_items": [],
  "source_confidence": "high|medium|low",
  "aud_usage_guidance": "..."
}}

Evidence:
{evidence_block}
""".strip()

    if len(prompt) > prompt_budget:
        return prompt[:prompt_budget].rstrip()

    return prompt


def get_source_role_instruction(source_role: str) -> str:
    if source_role == "fdd":
        return (
            "FDD is the golden source. Label it as the highest authority for "
            "business process, requirements, and functional behavior."
        )

    if source_role == "config_workbook":
        return (
            "Summarize configuration facts and setup details. State that the "
            "configuration workbook validates or enriches understanding and "
            "should not be copied blindly as primary narrative unless FDD or KT "
            "material supports it."
        )

    if source_role in {"kt_transcript", "kt_session"}:
        return (
            "Summarize presenter emphasis, corrections, Q&A, deferred items, "
            "and screenshot relevance when those appear in the evidence."
        )

    if source_role == "kt_ppt":
        return (
            "Summarize slide topics, tables, screenshots/images, and process "
            "or configuration topics visible in the evidence."
        )

    if source_role == "final_aud_sample":
        return (
            "Summarize style and structure only. Do not treat sample business "
            "content as authoritative for this project."
        )

    return (
        "Summarize only supported source details and explain how the evidence "
        "may enrich or validate the AUD."
    )


def build_bounded_evidence_block(
    evidence_items: list[EvidenceItem],
    max_chars: int,
) -> str:
    lines: list[str] = []
    used_chars = 0

    for index, item in enumerate(
        sorted(evidence_items, key=lambda evidence: (-evidence.priority, evidence.created_at)),
        start=1,
    ):
        text = (item.text or "").strip().replace("\r\n", "\n")

        if not text:
            text = "<No text evidence available>"

        if len(text) > EVIDENCE_PREVIEW_CHAR_LIMIT:
            text = f"{text[:EVIDENCE_PREVIEW_CHAR_LIMIT].rstrip()}\n<evidence truncated>"

        line = (
            f"[{index}] type={item.evidence_type}; "
            f"title={item.title or 'Untitled'}; "
            f"priority={item.priority}; confidence={item.confidence}\n{text}\n"
        )

        if used_chars + len(line) > max_chars:
            lines.append("<additional evidence omitted due to prompt length limit>")
            break

        lines.append(line)
        used_chars += len(line)

    return "\n".join(lines) if lines else "<No evidence available>"


def upsert_source_summary(
    session: Session,
    *,
    project_id: str,
    group: EvidenceSourceGroup,
    summary_payload: dict,
) -> SourceSummary:
    summary_type = get_summary_type(group.source_role)
    summary_text = str(summary_payload.get("summary") or "").strip()

    if not summary_text:
        summary_text = "<Summary not available from provided evidence>"

    statement = select(SourceSummary).where(
        SourceSummary.project_id == project_id,
        SourceSummary.source_uploaded_file_id == group.source_uploaded_file_id,
        SourceSummary.source_role == group.source_role,
        SourceSummary.summary_type == summary_type,
    )
    existing_summary = session.scalar(statement)
    summary_json = json.dumps(summary_payload, ensure_ascii=False)

    if existing_summary is not None:
        existing_summary.summary_text = summary_text
        existing_summary.summary_json = summary_json
        return existing_summary

    source_summary = SourceSummary(
        project_id=project_id,
        source_uploaded_file_id=group.source_uploaded_file_id,
        source_role=group.source_role,
        summary_type=summary_type,
        summary_text=summary_text,
        summary_json=summary_json,
    )
    session.add(source_summary)
    return source_summary


def generate_source_summaries_ai(
    session: Session,
    project_id: str,
    llm_service: LLMService | None = None,
    settings: Settings | None = None,
) -> SourceSummaryGenerationResult:
    resolved_settings = settings or get_settings()

    if llm_service is None and resolved_settings.LLM_PROVIDER.strip().lower() == "none":
        raise LLMConfigurationError(
            "LLM_PROVIDER must be configured before generating AI source summaries."
        )

    resolved_llm_service = llm_service or build_llm_service(resolved_settings)
    evidence_items = list(
        session.scalars(
            select(EvidenceItem)
            .where(EvidenceItem.project_id == project_id)
            .order_by(EvidenceItem.priority.desc(), EvidenceItem.created_at.asc())
        )
    )
    groups = group_evidence_items(evidence_items)
    summaries: list[SourceSummary] = []
    warnings: list[str] = []

    for group in groups:
        try:
            prompt = build_source_summary_prompt(group, settings=resolved_settings)
            payload = resolved_llm_service.generate_json(
                prompt,
                schema_name="source_summary",
            )
            normalized_payload = normalize_summary_payload(payload, group.source_role)
            source_summary = upsert_source_summary(
                session,
                project_id=project_id,
                group=group,
                summary_payload=normalized_payload,
            )
            session.commit()
            session.refresh(source_summary)
            summaries.append(source_summary)
        except Exception as error:
            session.rollback()
            error_message = "".join(
                format_exception_only(type(error), error)
            ).strip()
            warnings.append(
                f"{group.source_role}/{group.source_uploaded_file_id or 'no-file'}: "
                f"{error_message}"
            )

    return SourceSummaryGenerationResult(summaries=summaries, warnings=warnings)

from __future__ import annotations

import json
from dataclasses import dataclass
from traceback import format_exception_only
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import AUDSectionDraft, OpenPoint, SectionEvidencePack
from app.services.llm import (
    LLMConfigurationError,
    LLMInvalidJSONError,
    LLMService,
    build_llm_service,
)
from app.services.llm.base import get_prompt_body_budget
from app.services.section_evidence_pack import build_section_evidence_packs

CONFIDENCE_VALUES = {"high", "medium", "low"}
LIST_FIELDS = {
    "used_evidence_item_ids",
    "included_tables",
    "included_images",
    "unsupported_details",
    "open_point_candidates",
    "placeholders",
}


@dataclass
class SectionDraftGenerationResult:
    drafts: list[AUDSectionDraft]
    warnings: list[str]


def parse_pack_json(pack: SectionEvidencePack) -> dict[str, Any]:
    try:
        parsed = json.loads(pack.pack_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Section evidence pack {pack.id} contains invalid JSON.") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"Section evidence pack {pack.id} JSON must be an object.")

    return parsed


def list_section_evidence_packs(
    session: Session,
    project_id: str,
) -> list[SectionEvidencePack]:
    return list(
        session.scalars(
            select(SectionEvidencePack)
            .where(SectionEvidencePack.project_id == project_id)
            .order_by(SectionEvidencePack.created_at.asc())
        )
    )


def ensure_section_evidence_packs(
    session: Session,
    project_id: str,
    settings: Settings,
) -> list[SectionEvidencePack]:
    packs = list_section_evidence_packs(session, project_id)
    if packs:
        return packs

    return build_section_evidence_packs(session, project_id, settings=settings)


def as_string_list(value: Any) -> list[str]:
    if value is None:
        return []

    if not isinstance(value, list):
        value = [value]

    return [str(item) for item in value if str(item).strip()]


def ensure_json_list(value: Any) -> list[Any]:
    if value is None:
        return []

    return value if isinstance(value, list) else [value]


def has_supported_evidence(pack_payload: dict[str, Any]) -> bool:
    return any(
        pack_payload.get(bucket)
        for bucket in (
            "primary_evidence",
            "supporting_evidence",
            "configuration_evidence",
            "transcript_context",
            "image_candidates",
            "table_candidates",
        )
    )


def build_section_draft_prompt(
    pack_payload: dict[str, Any],
    settings: Settings | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    section_id = str(pack_payload.get("section_id") or "")
    section_title = str(pack_payload.get("section_title") or "")
    evidence_pack = json.dumps(pack_payload, ensure_ascii=False, separators=(",", ":"))
    prompt = f"""
You are a senior Oracle SCM functional consultant preparing an Application Understanding Document section.

Business rules:
- Use only evidence in the evidence pack.
- Do not invent missing customer, process, or configuration details.
- FDD is the golden source. If lower-priority evidence conflicts with FDD, FDD wins.
- If information is unclear, add a placeholder or propose an Open Point.
- Do not include generic Oracle SCM facts unless supported by the evidence pack.
- Use professional AUD language with a customer-facing but internally reviewable tone.
- If the section has no supported evidence, produce a clear placeholder and low confidence.
- Write Word-document-ready prose in draft_text.
- Do not include citations inside draft_text.
- Preserve used evidence item IDs in used_evidence_item_ids.

Return strict JSON only with this exact object shape:
{{
  "section_id": "{section_id}",
  "title": "{section_title}",
  "draft_text": "...",
  "confidence": "high|medium|low",
  "used_evidence_item_ids": [],
  "included_tables": [],
  "included_images": [],
  "unsupported_details": [],
  "open_point_candidates": [],
  "placeholders": []
}}

Evidence pack:
{evidence_pack}
""".strip()
    max_chars = get_prompt_body_budget(resolved_settings.OCI_GENAI_MAX_INPUT_CHARS)

    if len(prompt) <= max_chars:
        return prompt

    return prompt[:max_chars].rstrip()


def normalize_section_draft_payload(
    payload: dict[str, Any],
    pack_payload: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise LLMInvalidJSONError("Section draft response must be a JSON object.")

    section_id = str(payload.get("section_id") or pack_payload.get("section_id") or "")
    title = str(payload.get("title") or pack_payload.get("section_title") or "").strip()
    draft_text = str(payload.get("draft_text") or "").strip()
    confidence = str(payload.get("confidence") or "medium").lower()

    if not section_id:
        raise LLMInvalidJSONError("Section draft response missing section_id.")

    if not title:
        raise LLMInvalidJSONError("Section draft response missing title.")

    if not draft_text:
        draft_text = "<Content not available in provided source material>"
        confidence = "low"

    if confidence not in CONFIDENCE_VALUES:
        confidence = "medium"

    if not has_supported_evidence(pack_payload):
        confidence = "low"
        draft_text = "<Content not available in provided source material>"

    normalized = {
        "section_id": section_id,
        "title": title,
        "draft_text": draft_text,
        "confidence": confidence,
    }

    for field in LIST_FIELDS:
        if field == "used_evidence_item_ids":
            normalized[field] = as_string_list(payload.get(field))
        else:
            normalized[field] = ensure_json_list(payload.get(field))

    if not has_supported_evidence(pack_payload) and not normalized["placeholders"]:
        normalized["placeholders"] = [draft_text]

    return normalized


def upsert_section_draft(
    session: Session,
    project_id: str,
    payload: dict[str, Any],
) -> AUDSectionDraft:
    existing_draft = session.scalar(
        select(AUDSectionDraft).where(
            AUDSectionDraft.project_id == project_id,
            AUDSectionDraft.section_id == payload["section_id"],
        )
    )
    draft_json = json.dumps(payload, ensure_ascii=False)

    if existing_draft is not None:
        existing_draft.title = payload["title"]
        existing_draft.draft_text = payload["draft_text"]
        existing_draft.draft_json = draft_json
        existing_draft.confidence = payload["confidence"]
        existing_draft.review_status = "draft"
        return existing_draft

    draft = AUDSectionDraft(
        project_id=project_id,
        section_id=payload["section_id"],
        title=payload["title"],
        draft_text=payload["draft_text"],
        draft_json=draft_json,
        confidence=payload["confidence"],
        review_status="draft",
    )
    session.add(draft)
    return draft


def normalize_open_point_candidate(
    value: Any,
    section_title: str,
) -> dict[str, str] | None:
    if isinstance(value, str):
        question = value.strip()
        topic = section_title
        evidence = value.strip()
    elif isinstance(value, dict):
        question = str(value.get("question") or value.get("text") or "").strip()
        topic = str(value.get("topic") or section_title).strip()
        evidence = str(value.get("evidence") or question).strip()
    else:
        return None

    if not question:
        return None

    return {
        "topic": topic or section_title,
        "question": question,
        "evidence": evidence or question,
    }


def normalize_key(value: str) -> str:
    return " ".join(value.strip().lower().split())


def insert_open_point_candidates(
    session: Session,
    project_id: str,
    section_title: str,
    candidates: list[Any],
) -> list[OpenPoint]:
    existing_questions = {
        normalize_key(question)
        for question in session.scalars(
            select(OpenPoint.question).where(OpenPoint.project_id == project_id)
        )
    }
    inserted: list[OpenPoint] = []

    for candidate_value in candidates:
        candidate = normalize_open_point_candidate(candidate_value, section_title)
        if candidate is None:
            continue

        key = normalize_key(candidate["question"])
        if not key or key in existing_questions:
            continue

        existing_questions.add(key)
        open_point = OpenPoint(
            project_id=project_id,
            topic=candidate["topic"],
            question=candidate["question"],
            status="Open",
            evidence=candidate["evidence"],
        )
        session.add(open_point)
        inserted.append(open_point)

    return inserted


def generate_section_drafts_ai(
    session: Session,
    project_id: str,
    llm_service: LLMService | None = None,
    settings: Settings | None = None,
) -> SectionDraftGenerationResult:
    resolved_settings = settings or get_settings()
    packs = ensure_section_evidence_packs(session, project_id, resolved_settings)

    if llm_service is None and resolved_settings.LLM_PROVIDER.strip().lower() == "none":
        raise LLMConfigurationError(
            "LLM_PROVIDER must be configured before generating AI section drafts."
        )

    resolved_llm_service = llm_service or build_llm_service(resolved_settings)
    drafts: list[AUDSectionDraft] = []
    warnings: list[str] = []

    for pack in packs:
        try:
            pack_payload = parse_pack_json(pack)
            prompt = build_section_draft_prompt(pack_payload, settings=resolved_settings)
            payload = resolved_llm_service.generate_json(
                prompt,
                schema_name="aud_section_draft",
            )
            normalized_payload = normalize_section_draft_payload(payload, pack_payload)
            draft = upsert_section_draft(session, project_id, normalized_payload)
            insert_open_point_candidates(
                session,
                project_id,
                normalized_payload["title"],
                normalized_payload["open_point_candidates"],
            )
            session.commit()
            session.refresh(draft)
            drafts.append(draft)
        except Exception as error:
            session.rollback()
            error_message = "".join(
                format_exception_only(type(error), error)
            ).strip()
            warnings.append(f"{pack.section_id}/{pack.section_title}: {error_message}")

    return SectionDraftGenerationResult(drafts=drafts, warnings=warnings)

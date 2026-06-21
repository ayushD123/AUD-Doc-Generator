from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import AUDPlan, AUDSectionDraft, EvidenceItem, OpenPoint, SourceSummary
from app.services.llm import (
    LLMConfigurationError,
    LLMInvalidJSONError,
    LLMService,
    build_llm_service,
)
from app.services.llm.base import get_prompt_body_budget
from app.services.open_points_service import has_resolved_status, normalize_text

MAX_EXISTING_OPEN_POINTS = 100
MAX_CANDIDATES = 160
MAX_FDD_SUMMARIES = 8
TEXT_PREVIEW_CHARS = 700
OUTPUT_EXCLUSION_REASONS = {
    "resolved",
    "duplicate",
    "answered_by_fdd",
    "not_relevant",
}
MANUAL_ACTION_TERMS = [
    "add",
    "attach",
    "capture",
    "confirm",
    "insert",
    "manual",
    "provide",
    "replace",
    "review",
    "select",
    "upload",
]
SCREENSHOT_TERMS = ["screenshot", "screen shot", "image", "placeholder"]
TIMESTAMP_PATTERN = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
CONFLICT_TERMS = ["conflict", "contradict", "contradiction", "mismatch"]


@dataclass(frozen=True)
class OpenPointCandidateContext:
    candidate_id: str
    source: str
    text: str
    topic: str | None = None
    source_role: str | None = None
    evidence_item_ids: list[str] | None = None


@dataclass(frozen=True)
class OpenPointRefinementResult:
    open_points: list[OpenPoint]
    excluded_items: list[dict[str, str]]
    metadata: dict[str, Any]


def normalize_key(value: str) -> str:
    return " ".join(value.strip().lower().split())


def parse_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def get_refinement_metadata(value: str | None) -> dict[str, Any]:
    metadata = parse_json_object(value)
    if metadata.get("refinement_job_type") != "refine_open_points_ai":
        return {}

    return metadata


def get_open_point_evidence_text(open_point: OpenPoint) -> str:
    metadata = get_refinement_metadata(open_point.evidence)
    evidence_text = metadata.get("evidence_text")

    if isinstance(evidence_text, str) and evidence_text.strip():
        return evidence_text.strip()

    if metadata:
        reason = metadata.get("reason")
        if isinstance(reason, str) and reason.strip():
            return reason.strip()

        return normalize_text(open_point.question)

    return normalize_text(open_point.evidence or open_point.question)


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []

    return value if isinstance(value, list) else [value]


def normalize_string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in ensure_list(value) if str(item).strip()]


def truncate_text(value: str, limit: int = TEXT_PREVIEW_CHARS) -> str:
    normalized = normalize_text(value)
    if len(normalized) <= limit:
        return normalized

    return f"{normalized[:limit].rstrip()}..."


def list_existing_open_points(session: Session, project_id: str) -> list[OpenPoint]:
    return list(
        session.scalars(
            select(OpenPoint)
            .where(OpenPoint.project_id == project_id)
            .order_by(OpenPoint.created_at.asc())
            .limit(MAX_EXISTING_OPEN_POINTS)
        )
    )


def get_latest_aud_plan(session: Session, project_id: str) -> AUDPlan | None:
    return session.scalars(
        select(AUDPlan)
        .where(AUDPlan.project_id == project_id)
        .order_by(AUDPlan.created_at.desc())
    ).first()


def iter_candidate_texts(value: Any) -> list[str]:
    candidates: list[str] = []

    for item in ensure_list(value):
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(
                item.get("question")
                or item.get("text")
                or item.get("description")
                or item.get("item")
                or ""
            ).strip()
        else:
            text = ""

        if text:
            candidates.append(text)

    return candidates


def gather_source_summary_candidates(
    session: Session,
    project_id: str,
) -> list[OpenPointCandidateContext]:
    summaries = list(
        session.scalars(
            select(SourceSummary)
            .where(SourceSummary.project_id == project_id)
            .order_by(SourceSummary.created_at.asc())
        )
    )
    candidates: list[OpenPointCandidateContext] = []

    for summary in summaries:
        summary_json = parse_json_object(summary.summary_json)
        for index, text in enumerate(
            iter_candidate_texts(summary_json.get("open_or_unresolved_items")),
            start=1,
        ):
            candidates.append(
                OpenPointCandidateContext(
                    candidate_id=f"source_summary:{summary.id}:open:{index}",
                    source="source_summary",
                    source_role=summary.source_role,
                    topic=summary.summary_type,
                    text=text,
                )
            )

    return candidates


def gather_aud_plan_candidates(
    session: Session,
    project_id: str,
) -> list[OpenPointCandidateContext]:
    aud_plan = get_latest_aud_plan(session, project_id)
    if aud_plan is None:
        return []

    plan_payload = parse_json_object(aud_plan.plan_json)
    ai_enhanced_plan = plan_payload.get("ai_enhanced_plan")
    candidate_values: list[Any] = []

    if isinstance(ai_enhanced_plan, dict):
        candidate_values.extend(ensure_list(ai_enhanced_plan.get("open_point_candidates")))

    candidate_values.extend(ensure_list(plan_payload.get("open_point_candidates")))

    return [
        OpenPointCandidateContext(
            candidate_id=f"aud_plan:{aud_plan.id}:open:{index}",
            source="aud_plan",
            topic="AUD Plan",
            text=text,
        )
        for index, text in enumerate(iter_candidate_texts(candidate_values), start=1)
    ]


def gather_section_draft_candidates(
    session: Session,
    project_id: str,
) -> list[OpenPointCandidateContext]:
    drafts = list(
        session.scalars(
            select(AUDSectionDraft)
            .where(AUDSectionDraft.project_id == project_id)
            .order_by(AUDSectionDraft.created_at.asc())
        )
    )
    candidates: list[OpenPointCandidateContext] = []

    for draft in drafts:
        draft_json = parse_json_object(draft.draft_json)
        for index, text in enumerate(
            iter_candidate_texts(draft_json.get("open_point_candidates")),
            start=1,
        ):
            evidence_ids = []
            if isinstance(draft_json, dict):
                evidence_ids = normalize_string_list(
                    draft_json.get("used_evidence_item_ids")
                )
            candidates.append(
                OpenPointCandidateContext(
                    candidate_id=f"section_draft:{draft.id}:open:{index}",
                    source="section_draft",
                    topic=draft.title,
                    text=text,
                    evidence_item_ids=evidence_ids,
                )
            )

    return candidates


def gather_open_point_candidates(
    session: Session,
    project_id: str,
) -> list[OpenPointCandidateContext]:
    candidates = (
        gather_source_summary_candidates(session, project_id)
        + gather_aud_plan_candidates(session, project_id)
        + gather_section_draft_candidates(session, project_id)
    )

    return candidates[:MAX_CANDIDATES]


def list_fdd_summary_context(session: Session, project_id: str) -> list[dict[str, str]]:
    summaries = list(
        session.scalars(
            select(SourceSummary)
            .where(
                SourceSummary.project_id == project_id,
                SourceSummary.source_role == "fdd",
            )
            .order_by(SourceSummary.created_at.asc())
            .limit(MAX_FDD_SUMMARIES)
        )
    )
    return [
        {
            "id": summary.id,
            "summary_text": truncate_text(summary.summary_text),
        }
        for summary in summaries
    ]


def project_has_fdd_context(session: Session, project_id: str) -> bool:
    if list_fdd_summary_context(session, project_id):
        return True

    aud_plan = get_latest_aud_plan(session, project_id)
    if aud_plan is None:
        return False

    return (
        '"source_role_basis": "fdd"' in aud_plan.plan_json
        or '"fdd"' in aud_plan.plan_json
    )


def list_evidence_role_by_id(session: Session, project_id: str) -> dict[str, str]:
    evidence_items = session.scalars(
        select(EvidenceItem).where(EvidenceItem.project_id == project_id)
    )
    return {
        evidence_item.id: evidence_item.source_role or ""
        for evidence_item in evidence_items
    }


def list_evidence_item_by_id(session: Session, project_id: str) -> dict[str, EvidenceItem]:
    evidence_items = session.scalars(
        select(EvidenceItem).where(EvidenceItem.project_id == project_id)
    )
    return {evidence_item.id: evidence_item for evidence_item in evidence_items}


def build_refine_open_points_prompt(
    *,
    existing_open_points: list[OpenPoint],
    candidates: list[OpenPointCandidateContext],
    fdd_context: list[dict[str, str]],
    settings: Settings | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    max_chars = get_prompt_body_budget(resolved_settings.OCI_GENAI_MAX_INPUT_CHARS)
    existing_limit = len(existing_open_points)
    candidate_limit = len(candidates)
    fdd_context_limit = len(fdd_context)
    text_preview_chars = TEXT_PREVIEW_CHARS

    while True:
        prompt = render_refine_open_points_prompt(
            existing_open_points=existing_open_points[:existing_limit],
            candidates=candidates[:candidate_limit],
            fdd_context=fdd_context[:fdd_context_limit],
            text_preview_chars=text_preview_chars,
        )

        if len(prompt) <= max_chars:
            return prompt

        if candidate_limit > 40:
            candidate_limit = max(40, candidate_limit // 2)
        elif existing_limit > 25:
            existing_limit = max(25, existing_limit // 2)
        elif text_preview_chars > 160:
            text_preview_chars = max(160, text_preview_chars // 2)
        elif fdd_context_limit > 3:
            fdd_context_limit = max(3, fdd_context_limit // 2)
        elif candidate_limit > 0:
            candidate_limit = 0
        elif existing_limit > 0:
            existing_limit = 0
        elif fdd_context_limit > 0:
            fdd_context_limit = 0
        else:
            raise ValueError(
                "AI Open Points refinement prompt cannot fit within the configured "
                "OCI_GENAI_MAX_INPUT_CHARS safeguard without corrupting JSON input."
            )


def render_refine_open_points_prompt(
    *,
    existing_open_points: list[OpenPoint],
    candidates: list[OpenPointCandidateContext],
    fdd_context: list[dict[str, str]],
    text_preview_chars: int,
) -> str:
    prompt_payload = {
        "existing_open_points": [
            {
                "id": open_point.id,
                "topic": open_point.topic,
                "question": truncate_text(
                    open_point.question,
                    limit=text_preview_chars,
                ),
                "status": open_point.status,
                "evidence": truncate_text(
                    get_open_point_evidence_text(open_point),
                    limit=text_preview_chars,
                ),
            }
            for open_point in existing_open_points
        ],
        "open_point_candidates": [
            {
                "candidate_id": candidate.candidate_id,
                "source": candidate.source,
                "topic": candidate.topic,
                "source_role": candidate.source_role,
                "text": truncate_text(candidate.text, limit=text_preview_chars),
                "evidence_item_ids": candidate.evidence_item_ids or [],
            }
            for candidate in candidates
        ],
        "fdd_context": [
            {
                "id": item.get("id"),
                "summary_text": truncate_text(
                    str(item.get("summary_text") or ""),
                    limit=text_preview_chars,
                ),
            }
            for item in fdd_context
        ],
    }
    return f"""
Refine Open Points for an Oracle Application Understanding Document.

Business rules:
- Include only unresolved questions or manual actions.
- Convert raw fragments into clear consultant/customer clarification questions.
- Exclude items marked Closed, Resolved, Aligned, or Done.
- Exclude items answered by FDD or the final approved AUD sample.
- Exclude duplicates and return the cleanest wording once.
- Do not include transcript filler.
- Timestamp-based screenshot placeholders are Open Points only when a manual action is required.
- FDD is the golden source. If FDD provides a clear answer, do not create an Open Point from lower-priority conflict.
- If FDD says needs more discussion, to be confirmed, TBD, pending, or awaiting confirmation, include an Open Point.
- Clean wording, classify the topic, and keep status exactly "Open" for included items.
- Use only the provided inputs. Do not invent new project issues.

Return strict JSON only with this exact object shape:
{{
  "open_points": [
    {{
      "topic": "...",
      "question": "...",
      "status": "Open",
      "source_open_point_ids": [],
      "evidence_item_ids": [],
      "reason": "..."
    }}
  ],
  "excluded_items": [
    {{
      "text": "...",
      "reason": "resolved|duplicate|answered_by_fdd|not_relevant"
    }}
  ]
}}

Inputs:
{json.dumps(prompt_payload, ensure_ascii=False, separators=(",", ":"))}
""".strip()


def is_screenshot_timestamp_without_manual_action(text: str) -> bool:
    normalized = text.lower()
    has_screenshot_placeholder = any(term in normalized for term in SCREENSHOT_TERMS)
    has_timestamp = TIMESTAMP_PATTERN.search(normalized) is not None

    if not has_screenshot_placeholder or not has_timestamp:
        return False

    return not any(
        re.search(rf"\b{re.escape(term)}\b", normalized)
        for term in MANUAL_ACTION_TERMS
    )


def is_lower_priority_conflict_answered_by_fdd(
    *,
    text: str,
    source_open_point_ids: list[str],
    evidence_item_ids: list[str],
    existing_role_by_open_point_id: dict[str, str],
    evidence_role_by_id: dict[str, str],
    fdd_present: bool,
) -> bool:
    if not fdd_present:
        return False

    combined_text = text.lower()
    if not any(term in combined_text for term in CONFLICT_TERMS):
        return False

    source_roles = {
        existing_role_by_open_point_id.get(open_point_id, "")
        for open_point_id in source_open_point_ids
    }
    source_roles.update(
        evidence_role_by_id.get(evidence_item_id, "")
        for evidence_item_id in evidence_item_ids
    )
    source_roles.discard("")

    return "fdd" not in source_roles


def normalize_refinement_payload(
    payload: dict[str, Any],
    *,
    existing_role_by_open_point_id: dict[str, str],
    evidence_role_by_id: dict[str, str],
    fdd_present: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    if not isinstance(payload, dict):
        raise LLMInvalidJSONError("Open point refinement response must be an object.")

    open_points = payload.get("open_points")
    excluded_items = payload.get("excluded_items", [])

    if not isinstance(open_points, list):
        raise LLMInvalidJSONError("Open point refinement missing open_points list.")

    if not isinstance(excluded_items, list):
        raise LLMInvalidJSONError("Open point refinement missing excluded_items list.")

    normalized_open_points: list[dict[str, Any]] = []
    normalized_exclusions: list[dict[str, str]] = []
    seen_questions: set[str] = set()

    for raw_exclusion in excluded_items:
        if not isinstance(raw_exclusion, dict):
            continue

        text = str(raw_exclusion.get("text") or "").strip()
        reason = str(raw_exclusion.get("reason") or "not_relevant").strip().lower()
        normalized_exclusions.append(
            {
                "text": text,
                "reason": reason if reason in OUTPUT_EXCLUSION_REASONS else "not_relevant",
            }
        )

    for raw_open_point in open_points:
        if not isinstance(raw_open_point, dict):
            continue

        topic = str(raw_open_point.get("topic") or "Open Point").strip()
        question = normalize_text(str(raw_open_point.get("question") or ""))
        status = str(raw_open_point.get("status") or "Open").strip()
        source_open_point_ids = normalize_string_list(
            raw_open_point.get("source_open_point_ids")
        )
        evidence_item_ids = normalize_string_list(raw_open_point.get("evidence_item_ids"))
        reason = str(raw_open_point.get("reason") or "").strip()
        combined_text = f"{topic} {question} {reason}"

        if not question:
            continue

        if status.lower() != "open" or has_resolved_status(combined_text):
            normalized_exclusions.append({"text": question, "reason": "resolved"})
            continue

        if is_screenshot_timestamp_without_manual_action(combined_text):
            normalized_exclusions.append({"text": question, "reason": "not_relevant"})
            continue

        if is_lower_priority_conflict_answered_by_fdd(
            text=combined_text,
            source_open_point_ids=source_open_point_ids,
            evidence_item_ids=evidence_item_ids,
            existing_role_by_open_point_id=existing_role_by_open_point_id,
            evidence_role_by_id=evidence_role_by_id,
            fdd_present=fdd_present,
        ):
            normalized_exclusions.append({"text": question, "reason": "answered_by_fdd"})
            continue

        key = normalize_key(question)
        if key in seen_questions:
            normalized_exclusions.append({"text": question, "reason": "duplicate"})
            continue

        seen_questions.add(key)
        normalized_open_points.append(
            {
                "topic": topic or "Open Point",
                "question": question,
                "status": "Open",
                "source_open_point_ids": source_open_point_ids,
                "evidence_item_ids": evidence_item_ids,
                "reason": reason,
            }
        )

    return normalized_open_points, normalized_exclusions


def is_refined_open_point(open_point: OpenPoint) -> bool:
    return open_point.source_type == "llm_enhanced" or bool(
        get_refinement_metadata(open_point.evidence)
    )


def build_existing_role_map(open_points: list[OpenPoint]) -> dict[str, str]:
    role_map: dict[str, str] = {}

    for open_point in open_points:
        metadata = parse_json_object(open_point.evidence)
        source_role = metadata.get("source_role")
        role_map[open_point.id] = source_role if isinstance(source_role, str) else ""

    return role_map


def build_refined_evidence_text(
    payload: dict[str, Any],
    *,
    existing_by_id: dict[str, OpenPoint],
    candidate_by_id: dict[str, OpenPointCandidateContext],
    evidence_item_by_id: dict[str, EvidenceItem],
) -> str:
    snippets: list[str] = []
    seen: set[str] = set()

    def add_snippet(value: str | None) -> None:
        text = normalize_text(value or "")
        key = normalize_key(text)
        if not key or key in seen:
            return

        seen.add(key)
        snippets.append(text)

    for source_id in payload["source_open_point_ids"]:
        existing_open_point = existing_by_id.get(source_id)
        if existing_open_point is not None:
            add_snippet(get_open_point_evidence_text(existing_open_point))
            continue

        candidate = candidate_by_id.get(source_id)
        if candidate is not None:
            add_snippet(candidate.text)

    for evidence_item_id in payload["evidence_item_ids"]:
        evidence_item = evidence_item_by_id.get(evidence_item_id)
        if evidence_item is not None:
            add_snippet(evidence_item.text or evidence_item.title)

    if not snippets:
        add_snippet(payload.get("reason"))

    if not snippets:
        add_snippet(payload["question"])

    return "\n".join(snippets)


def apply_refined_open_points(
    session: Session,
    project_id: str,
    refined_payloads: list[dict[str, Any]],
    excluded_items: list[dict[str, str]],
    metadata: dict[str, Any],
    candidates: list[OpenPointCandidateContext],
) -> list[OpenPoint]:
    existing_open_points = list_existing_open_points(session, project_id)
    existing_by_question = {
        normalize_key(open_point.question): open_point for open_point in existing_open_points
    }
    existing_by_id = {open_point.id: open_point for open_point in existing_open_points}
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    evidence_item_by_id = list_evidence_item_by_id(session, project_id)
    created_or_updated: list[OpenPoint] = []

    for payload in refined_payloads:
        question_key = normalize_key(payload["question"])
        source_ids = set(payload["source_open_point_ids"])

        for source_id in source_ids:
            existing = existing_by_id.get(source_id)
            if existing is not None and existing.status != "Removed":
                existing.status = "Removed"
                existing.refinement_status = "refined"

        existing_same_question = existing_by_question.get(question_key)
        if existing_same_question is not None:
            if is_refined_open_point(existing_same_question):
                open_point = existing_same_question
                open_point.topic = payload["topic"]
                open_point.question = payload["question"]
                open_point.status = "Open"
                open_point.source_type = "llm_enhanced"
                open_point.refinement_status = "refined"
            else:
                existing_same_question.status = "Removed"
                existing_same_question.refinement_status = "refined"
                open_point = OpenPoint(
                    project_id=project_id,
                    topic=payload["topic"],
                    question=payload["question"],
                    status="Open",
                    source_type="llm_enhanced",
                    refinement_status="refined",
                    raw_source_open_point_ids_json=json.dumps(
                        payload["source_open_point_ids"]
                    ),
                )
                session.add(open_point)
        else:
            open_point = OpenPoint(
                project_id=project_id,
                topic=payload["topic"],
                question=payload["question"],
                status="Open",
                source_type="llm_enhanced",
                refinement_status="refined",
                raw_source_open_point_ids_json=json.dumps(
                    payload["source_open_point_ids"]
                ),
            )
            session.add(open_point)

        evidence_text = build_refined_evidence_text(
            payload,
            existing_by_id=existing_by_id,
            candidate_by_id=candidate_by_id,
            evidence_item_by_id=evidence_item_by_id,
        )
        open_point.evidence = json.dumps(
            {
                "refinement_job_type": "refine_open_points_ai",
                "evidence_text": evidence_text,
                "source_open_point_ids": payload["source_open_point_ids"],
                "evidence_item_ids": payload["evidence_item_ids"],
                "reason": payload["reason"],
                "excluded_items": excluded_items,
                "metadata": metadata,
            },
            ensure_ascii=False,
        )
        open_point.source_type = "llm_enhanced"
        open_point.refinement_status = "refined"
        open_point.raw_source_open_point_ids_json = json.dumps(
            payload["source_open_point_ids"]
        )
        created_or_updated.append(open_point)

    return created_or_updated


def mark_open_point_refinement_failed(
    session: Session,
    project_id: str,
) -> int:
    open_points = list_existing_open_points(session, project_id)
    marked_count = 0

    for open_point in open_points:
        if (
            open_point.source_type in {"raw_extracted", "fallback"}
            and open_point.refinement_status == "pending"
        ):
            open_point.refinement_status = "failed"
            marked_count += 1

    session.commit()
    return marked_count


def refine_open_points_ai(
    session: Session,
    project_id: str,
    llm_service: LLMService | None = None,
    settings: Settings | None = None,
) -> OpenPointRefinementResult:
    resolved_settings = settings or get_settings()

    if llm_service is None and resolved_settings.LLM_PROVIDER.strip().lower() == "none":
        raise LLMConfigurationError(
            "LLM_PROVIDER must be configured before refining Open Points with AI."
        )

    existing_open_points = list_existing_open_points(session, project_id)
    candidates = gather_open_point_candidates(session, project_id)
    fdd_context = list_fdd_summary_context(session, project_id)
    fdd_present = bool(fdd_context) or project_has_fdd_context(session, project_id)
    prompt = build_refine_open_points_prompt(
        existing_open_points=existing_open_points,
        candidates=candidates,
        fdd_context=fdd_context,
        settings=resolved_settings,
    )
    resolved_llm_service = llm_service or build_llm_service(resolved_settings)
    payload = resolved_llm_service.generate_json(
        prompt,
        schema_name="open_points_ai_refinement",
    )
    refined_payloads, excluded_items = normalize_refinement_payload(
        payload,
        existing_role_by_open_point_id=build_existing_role_map(existing_open_points),
        evidence_role_by_id=list_evidence_role_by_id(session, project_id),
        fdd_present=fdd_present,
    )
    metadata = {
        "existing_open_point_count": len(existing_open_points),
        "candidate_count": len(candidates),
        "fdd_context_count": len(fdd_context),
        "excluded_count": len(excluded_items),
    }
    open_points = apply_refined_open_points(
        session,
        project_id,
        refined_payloads,
        excluded_items,
        metadata,
        candidates,
    )
    session.commit()

    for open_point in open_points:
        session.refresh(open_point)

    return OpenPointRefinementResult(
        open_points=open_points,
        excluded_items=excluded_items,
        metadata=metadata,
    )

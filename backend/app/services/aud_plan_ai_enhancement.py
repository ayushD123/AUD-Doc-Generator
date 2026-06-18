from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import AUDPlan, EvidenceItem, SourceSummary
from app.services.aud_plan_service import generate_aud_plan
from app.services.llm import LLMConfigurationError, LLMInvalidJSONError, LLMService, build_llm_service
from app.services.llm.base import get_prompt_body_budget
from app.services.source_priority_service import build_source_priority_report

MAX_SOURCE_SUMMARIES = 20
MAX_EVIDENCE_ITEMS = 40
EVIDENCE_TEXT_PREVIEW_CHARS = 350
SOURCE_SUMMARY_PREVIEW_CHARS = 700
MAX_OUTPUT_SECTIONS = 25
EXPECTED_CONTENT_TYPES = {
    "narrative",
    "table",
    "process_flow",
    "configuration",
    "open_points",
    "image_supported",
}
CONTENT_PRIORITIES = {"fdd", "ppt", "transcript", "config", "mixed"}
MISSING_INFO_HANDLING_VALUES = {"omit", "placeholder", "open_point", "blank"}
CONFIDENCE_VALUES = {"high", "medium", "low"}


def get_latest_aud_plan(session: Session, project_id: str) -> AUDPlan | None:
    return session.scalars(
        select(AUDPlan)
        .where(AUDPlan.project_id == project_id)
        .order_by(AUDPlan.created_at.desc())
    ).first()


def ensure_aud_plan(session: Session, project_id: str) -> AUDPlan:
    aud_plan = get_latest_aud_plan(session, project_id)

    if aud_plan is not None:
        return aud_plan

    return generate_aud_plan(session, project_id)


def parse_plan_json(aud_plan: AUDPlan) -> dict[str, Any]:
    try:
        parsed = json.loads(aud_plan.plan_json)
    except json.JSONDecodeError as exc:
        raise ValueError("Existing deterministic AUD plan JSON is invalid.") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Existing deterministic AUD plan JSON must be an object.")

    return parsed


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def get_source_summaries(session: Session, project_id: str) -> list[SourceSummary]:
    return list(
        session.scalars(
            select(SourceSummary)
            .where(SourceSummary.project_id == project_id)
            .order_by(SourceSummary.source_role.asc(), SourceSummary.created_at.asc())
            .limit(MAX_SOURCE_SUMMARIES)
        )
    )


def get_top_evidence_items(session: Session, project_id: str) -> list[EvidenceItem]:
    return list(
        session.scalars(
            select(EvidenceItem)
            .where(EvidenceItem.project_id == project_id)
            .order_by(EvidenceItem.priority.desc(), EvidenceItem.created_at.asc())
            .limit(MAX_EVIDENCE_ITEMS)
        )
    )


def parse_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def compact_plan_for_prompt(plan_payload: dict[str, Any]) -> dict[str, Any]:
    compact_sections: list[dict[str, Any]] = []

    for section in ensure_list(plan_payload.get("sections"))[:MAX_OUTPUT_SECTIONS]:
        if not isinstance(section, dict):
            continue

        compact_sections.append(
            {
                "section_id": section.get("section_id"),
                "title": section.get("title"),
                "source_role_basis": section.get("source_role_basis"),
                "source_mapping": section.get("source_mapping"),
            }
        )

    return {
        "project_id": plan_payload.get("project_id"),
        "generation_basis": plan_payload.get("generation_basis"),
        "default_template_required": plan_payload.get("default_template_required"),
        "sections": compact_sections,
    }


def compact_source_summary(summary: SourceSummary) -> dict[str, Any]:
    summary_json = parse_json_object(summary.summary_json)
    summary_text = summary.summary_text.strip()

    if len(summary_text) > SOURCE_SUMMARY_PREVIEW_CHARS:
        summary_text = f"{summary_text[:SOURCE_SUMMARY_PREVIEW_CHARS].rstrip()}..."

    return {
        "id": summary.id,
        "source_uploaded_file_id": summary.source_uploaded_file_id,
        "source_role": summary.source_role,
        "summary_type": summary.summary_type,
        "summary_text": summary_text,
        "important_topics": summary_json.get("important_topics", []),
        "tables_or_configurations": summary_json.get("tables_or_configurations", []),
        "processes": summary_json.get("processes", []),
        "screenshots_or_images_to_consider": summary_json.get(
            "screenshots_or_images_to_consider",
            [],
        ),
        "open_or_unresolved_items": summary_json.get("open_or_unresolved_items", []),
        "source_confidence": summary_json.get("source_confidence", "medium"),
        "aud_usage_guidance": summary_json.get("aud_usage_guidance", ""),
    }


def compact_evidence_item(evidence_item: EvidenceItem) -> dict[str, Any]:
    text = (evidence_item.text or "").strip()

    if len(text) > EVIDENCE_TEXT_PREVIEW_CHARS:
        text = f"{text[:EVIDENCE_TEXT_PREVIEW_CHARS].rstrip()}..."

    return {
        "id": evidence_item.id,
        "source_uploaded_file_id": evidence_item.source_uploaded_file_id,
        "evidence_type": evidence_item.evidence_type,
        "source_role": evidence_item.source_role,
        "title": evidence_item.title,
        "text": text,
        "priority": evidence_item.priority,
        "confidence": evidence_item.confidence,
    }


def build_enhance_aud_plan_prompt(
    *,
    deterministic_plan: dict[str, Any],
    source_priority_report: dict[str, Any],
    source_summaries: list[SourceSummary],
    evidence_items: list[EvidenceItem],
    settings: Settings | None = None,
) -> str:
    resolved_settings = settings or get_settings()
    prompt_payload = {
        "deterministic_aud_plan": compact_plan_for_prompt(deterministic_plan),
        "source_priority_report": source_priority_report,
        "source_summaries": [
            compact_source_summary(summary) for summary in source_summaries
        ],
        "top_evidence_items": [
            compact_evidence_item(evidence_item) for evidence_item in evidence_items
        ],
    }
    prompt = f"""
Enhance the deterministic AUD plan for later AUD drafting.

Authoritative business rules:
- Deterministic source priority remains authoritative.
- FDD is the golden source if present.
- If FDD conflicts with transcript, PPT, or configuration workbook, FDD wins.
- Explicit template controls structure if uploaded.
- Default SCM template is used only if no explicit template is uploaded.
- Do not include empty or unsupported sections.
- Do not include Documents Referred section for now.
- Reporting/RICEW sections are included only if mentioned or provided in evidence.
- Open Points includes unresolved items only.
- Configuration workbook validates and enriches; do not treat it as primary narrative when FDD exists and do not copy workbook rows blindly.
- PPT images should be included only based on KT transcript/presenter focus and relevance.
- Final AUD samples are style/reference only unless explicitly uploaded as template_aud.

Return strict JSON only with this exact object shape:
{{
  "document_strategy": {{
    "template_source": "...",
    "content_golden_source": "...",
    "default_template_required": true,
    "notes": []
  }},
  "sections": [
    {{
      "section_id": "...",
      "title": "...",
      "include_in_aud": true,
      "reason": "...",
      "source_roles": [],
      "source_summary_ids": [],
      "evidence_item_ids": [],
      "content_priority": "fdd|ppt|transcript|config|mixed",
      "expected_content_type": "narrative|table|process_flow|configuration|open_points|image_supported",
      "confidence": "high|medium|low",
      "missing_info_handling": "omit|placeholder|open_point|blank"
    }}
  ],
  "image_strategy": [],
  "table_strategy": [],
  "open_point_candidates": [],
  "warnings": []
}}

Output limits:
- Return no more than {MAX_OUTPUT_SECTIONS} sections.
- Return only sections that should be included in the AUD.
- Keep each reason under 160 characters.
- Use only IDs from the provided source summaries and evidence items.
- Keep source_summary_ids and evidence_item_ids to the strongest matches only.
- Use empty arrays for image_strategy, table_strategy, and open_point_candidates if uncertain.
- Do not write draft section content.

Inputs:
{json.dumps(prompt_payload, ensure_ascii=False, separators=(",", ":"))}
""".strip()

    max_chars = get_prompt_body_budget(resolved_settings.OCI_GENAI_MAX_INPUT_CHARS)
    if len(prompt) <= max_chars:
        return prompt

    return prompt[:max_chars].rstrip()


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []

    return value if isinstance(value, list) else [value]


def normalize_string_list(value: Any) -> list[str]:
    return [str(item) for item in ensure_list(value) if str(item).strip()]


def normalize_bool(value: Any) -> bool:
    return value if isinstance(value, bool) else bool(value)


def validate_and_normalize_ai_plan(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise LLMInvalidJSONError("Enhanced AUD plan response must be a JSON object.")

    document_strategy = payload.get("document_strategy")
    sections = payload.get("sections")

    if not isinstance(document_strategy, dict):
        raise LLMInvalidJSONError("Enhanced AUD plan missing document_strategy.")

    if not isinstance(sections, list):
        raise LLMInvalidJSONError("Enhanced AUD plan missing sections list.")

    normalized_sections: list[dict[str, Any]] = []

    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            raise LLMInvalidJSONError("Enhanced AUD plan section must be an object.")

        title = str(section.get("title") or "").strip()

        if not title:
            continue

        if normalize_key(title) == "documents-referred":
            continue

        content_priority = str(section.get("content_priority") or "mixed").lower()
        expected_content_type = str(
            section.get("expected_content_type") or "narrative"
        ).lower()
        confidence = str(section.get("confidence") or "medium").lower()
        missing_info_handling = str(
            section.get("missing_info_handling") or "placeholder"
        ).lower()

        normalized_sections.append(
            {
                "section_id": str(
                    section.get("section_id")
                    or f"ai-section-{index:03d}-{normalize_key(title) or 'untitled'}"
                ),
                "title": title,
                "include_in_aud": normalize_bool(section.get("include_in_aud", True)),
                "reason": str(section.get("reason") or ""),
                "source_roles": normalize_string_list(section.get("source_roles")),
                "source_summary_ids": normalize_string_list(
                    section.get("source_summary_ids")
                ),
                "evidence_item_ids": normalize_string_list(
                    section.get("evidence_item_ids")
                ),
                "content_priority": (
                    content_priority
                    if content_priority in CONTENT_PRIORITIES
                    else "mixed"
                ),
                "expected_content_type": (
                    expected_content_type
                    if expected_content_type in EXPECTED_CONTENT_TYPES
                    else "narrative"
                ),
                "confidence": confidence if confidence in CONFIDENCE_VALUES else "medium",
                "missing_info_handling": (
                    missing_info_handling
                    if missing_info_handling in MISSING_INFO_HANDLING_VALUES
                    else "placeholder"
                ),
            }
        )

    return {
        "document_strategy": {
            "template_source": str(document_strategy.get("template_source") or ""),
            "content_golden_source": str(
                document_strategy.get("content_golden_source") or ""
            ),
            "default_template_required": normalize_bool(
                document_strategy.get("default_template_required", False)
            ),
            "notes": normalize_string_list(document_strategy.get("notes")),
        },
        "sections": normalized_sections,
        "image_strategy": ensure_list(payload.get("image_strategy")),
        "table_strategy": ensure_list(payload.get("table_strategy")),
        "open_point_candidates": ensure_list(payload.get("open_point_candidates")),
        "warnings": normalize_string_list(payload.get("warnings")),
    }


def enhance_aud_plan_ai(
    session: Session,
    project_id: str,
    llm_service: LLMService | None = None,
    settings: Settings | None = None,
) -> AUDPlan:
    resolved_settings = settings or get_settings()

    if llm_service is None and resolved_settings.LLM_PROVIDER.strip().lower() == "none":
        raise LLMConfigurationError(
            "LLM_PROVIDER must be configured before enhancing the AUD plan."
        )

    aud_plan = ensure_aud_plan(session, project_id)
    deterministic_plan = parse_plan_json(aud_plan)
    source_priority_report = build_source_priority_report(session, project_id).model_dump()
    source_summaries = get_source_summaries(session, project_id)
    evidence_items = get_top_evidence_items(session, project_id)
    prompt = build_enhance_aud_plan_prompt(
        deterministic_plan=deterministic_plan,
        source_priority_report=source_priority_report,
        source_summaries=source_summaries,
        evidence_items=evidence_items,
        settings=resolved_settings,
    )
    resolved_llm_service = llm_service or build_llm_service(resolved_settings)
    enhanced_payload = resolved_llm_service.generate_json(
        prompt,
        schema_name="aud_plan_ai_enhancement",
    )
    normalized_enhanced_plan = validate_and_normalize_ai_plan(enhanced_payload)
    updated_plan = dict(deterministic_plan)
    updated_plan["ai_enhanced_plan"] = normalized_enhanced_plan
    aud_plan.plan_json = json.dumps(updated_plan, indent=2, ensure_ascii=False)
    session.add(aud_plan)
    session.commit()
    session.refresh(aud_plan)
    return aud_plan

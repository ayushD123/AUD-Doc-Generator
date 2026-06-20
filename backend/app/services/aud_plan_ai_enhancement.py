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
JSON_SCHEMA_MARKER_KEYS = {"$schema", "additionalProperties", "properties", "required"}
JSON_SCHEMA_VALUE_KEYS = {
    "$schema",
    "additionalProperties",
    "allOf",
    "anyOf",
    "default",
    "description",
    "enum",
    "examples",
    "format",
    "items",
    "maxItems",
    "minItems",
    "oneOf",
    "properties",
    "required",
    "title",
    "type",
}
AUD_PLAN_JSON_RETRY_SYSTEM_PROMPT = (
    "The previous AUD plan enhancement response could not be parsed as JSON. "
    "Return exactly one complete JSON object with top-level document_strategy "
    "and sections. Close every object and array. Do not include markdown, prose, "
    "comments, examples, ellipses, or trailing commas."
)
AUD_PLAN_SCHEMA_RETRY_SYSTEM_PROMPT = (
    "The previous AUD plan enhancement response parsed as JSON but did not match "
    "the required AUD plan schema. Return exactly one complete JSON object with "
    "top-level document_strategy and sections. The sections value must be an "
    "array of section objects. Do not return schema definitions, examples, "
    "section maps, markdown, prose, or the deterministic_aud_plan input object."
)
AUD_PLAN_WRAPPER_KEYS = (
    "ai_enhanced_plan",
    "enhanced_aud_plan",
    "enhanced_plan",
    "aud_generation_plan",
    "document_plan",
    "aud_plan",
    "plan",
    "output",
    "result",
    "response",
)
AUD_PLAN_SECTION_KEYS = (
    "sections",
    "aud_sections",
    "aud_document_sections",
    "aud_plan_sections",
    "aud_outline",
    "document_outline",
    "enhanced_sections",
    "enhanced_aud_sections",
    "document_sections",
    "outline",
    "recommended_sections",
    "section_mapping",
    "section_plan",
    "section_recommendations",
    "sections_to_include",
    "plan_sections",
)


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


def compact_source_summary(
    summary: SourceSummary,
    preview_chars: int = SOURCE_SUMMARY_PREVIEW_CHARS,
) -> dict[str, Any]:
    summary_json = parse_json_object(summary.summary_json)
    summary_text = summary.summary_text.strip()

    if len(summary_text) > preview_chars:
        summary_text = f"{summary_text[:preview_chars].rstrip()}..."

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


def compact_evidence_item(
    evidence_item: EvidenceItem,
    preview_chars: int = EVIDENCE_TEXT_PREVIEW_CHARS,
) -> dict[str, Any]:
    text = (evidence_item.text or "").strip()

    if len(text) > preview_chars:
        text = f"{text[:preview_chars].rstrip()}..."

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
    max_chars = get_prompt_body_budget(resolved_settings.OCI_GENAI_MAX_INPUT_CHARS)
    source_summary_limit = len(source_summaries)
    evidence_limit = len(evidence_items)
    source_summary_preview_chars = SOURCE_SUMMARY_PREVIEW_CHARS
    evidence_preview_chars = EVIDENCE_TEXT_PREVIEW_CHARS

    while True:
        prompt = render_enhance_aud_plan_prompt(
            deterministic_plan=deterministic_plan,
            source_priority_report=source_priority_report,
            source_summaries=source_summaries[:source_summary_limit],
            evidence_items=evidence_items[:evidence_limit],
            source_summary_preview_chars=source_summary_preview_chars,
            evidence_preview_chars=evidence_preview_chars,
        )

        if len(prompt) <= max_chars:
            return prompt

        if evidence_limit > 10:
            evidence_limit = max(10, evidence_limit // 2)
        elif source_summary_limit > 5:
            source_summary_limit = max(5, source_summary_limit // 2)
        elif evidence_preview_chars > 120:
            evidence_preview_chars = max(120, evidence_preview_chars // 2)
        elif source_summary_preview_chars > 200:
            source_summary_preview_chars = max(200, source_summary_preview_chars // 2)
        elif evidence_limit > 0:
            evidence_limit = 0
        elif source_summary_limit > 0:
            source_summary_limit = 0
        else:
            raise ValueError(
                "AI AUD plan enhancement prompt cannot fit within the configured "
                "OCI_GENAI_MAX_INPUT_CHARS safeguard without corrupting JSON input."
            )


def render_enhance_aud_plan_prompt(
    *,
    deterministic_plan: dict[str, Any],
    source_priority_report: dict[str, Any],
    source_summaries: list[SourceSummary],
    evidence_items: list[EvidenceItem],
    source_summary_preview_chars: int,
    evidence_preview_chars: int,
) -> str:
    prompt_payload = {
        "deterministic_aud_plan": compact_plan_for_prompt(deterministic_plan),
        "source_priority_report": source_priority_report,
        "source_summaries": [
            compact_source_summary(summary, preview_chars=source_summary_preview_chars)
            for summary in source_summaries
        ],
        "top_evidence_items": [
            compact_evidence_item(
                evidence_item,
                preview_chars=evidence_preview_chars,
            )
            for evidence_item in evidence_items
        ],
    }
    return f"""
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

Final reminder:
- Return one JSON object only.
- The top-level object must contain document_strategy and sections.
- Use the key sections exactly; do not use aud_sections, enhanced_sections, document_sections, section_plan, or plan_sections.
- Do not return the deterministic_aud_plan input object.
- Do not wrap the answer in another key unless that key is ai_enhanced_plan.

Inputs:
{json.dumps(prompt_payload, ensure_ascii=False, separators=(",", ":"))}
""".strip()


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

    payload = unwrap_ai_plan_payload(payload)
    document_strategy = payload.get("document_strategy")
    sections = extract_ai_plan_sections(payload)

    if not isinstance(sections, list):
        raise LLMInvalidJSONError(
            "Enhanced AUD plan missing sections list. "
            f"Payload preview: {build_payload_preview(payload)}"
        )

    if not isinstance(document_strategy, dict):
        document_strategy = build_default_document_strategy(payload)

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


def unwrap_ai_plan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if has_direct_ai_plan_sections(payload):
        return payload

    for key in AUD_PLAN_WRAPPER_KEYS:
        nested = payload.get(key)
        if isinstance(nested, dict):
            unwrapped = unwrap_ai_plan_payload(nested)
            if (
                isinstance(payload.get("document_strategy"), dict)
                and "document_strategy" not in unwrapped
            ):
                return {**unwrapped, "document_strategy": payload["document_strategy"]}
            return unwrapped

    return payload


def has_direct_ai_plan_sections(payload: dict[str, Any]) -> bool:
    for key in AUD_PLAN_SECTION_KEYS:
        value = payload.get(key)
        if normalize_sections_candidate(value):
            return True

    return False


def extract_ai_plan_sections(payload: dict[str, Any]) -> list[Any] | None:
    for key in AUD_PLAN_SECTION_KEYS:
        sections = normalize_sections_candidate(payload.get(key))
        if sections:
            return sections

    for key, value in payload.items():
        if key in {"document_strategy", "image_strategy", "table_strategy"}:
            continue
        if any(token in key.lower() for token in ("section", "outline")):
            sections = normalize_sections_candidate(value)
            if sections:
                return sections
        if isinstance(value, dict):
            nested_sections = extract_ai_plan_sections(value)
            if nested_sections:
                return nested_sections

    return None


def normalize_sections_candidate(value: Any) -> list[Any] | None:
    if isinstance(value, list):
        return value

    if not isinstance(value, dict):
        return None

    nested_sections = value.get("sections")
    if isinstance(nested_sections, list):
        return nested_sections

    if is_json_schema_like_dict(value):
        return None

    section_items: list[dict[str, Any]] = []
    for title, details in value.items():
        if isinstance(details, dict):
            if is_json_schema_like_dict(details):
                continue
            section = dict(details)
            section.setdefault("title", str(title))
            section_items.append(section)
        elif isinstance(details, str):
            section_items.append({"title": str(title), "reason": details})

    if not section_items:
        return None

    if any(str(section.get("title") or "").strip() for section in section_items):
        return section_items

    return None


def is_json_schema_like_dict(value: dict[str, Any]) -> bool:
    keys = set(value.keys())

    if JSON_SCHEMA_MARKER_KEYS & keys:
        return True

    if "type" not in keys:
        return False

    return keys <= JSON_SCHEMA_VALUE_KEYS


def build_payload_preview(payload: dict[str, Any]) -> str:
    try:
        preview = json.dumps(payload, ensure_ascii=False)
    except TypeError:
        preview = str(payload)

    preview = " ".join(preview.split())
    if len(preview) > 700:
        preview = f"{preview[:700].rstrip()}..."
    return preview or "<empty object>"


def build_default_document_strategy(payload: dict[str, Any]) -> dict[str, Any]:
    warnings = normalize_string_list(payload.get("warnings"))
    warnings.append(
        "LLM omitted document_strategy; backend applied source-priority defaults."
    )
    return {
        "template_source": str(
            payload.get("template_source") or "default_or_uploaded_template"
        ),
        "content_golden_source": str(
            payload.get("content_golden_source") or "fdd_if_present"
        ),
        "default_template_required": normalize_bool(
            payload.get("default_template_required", False)
        ),
        "notes": warnings,
    }


def generate_validated_enhanced_plan(
    llm_service: LLMService,
    prompt: str,
) -> dict[str, Any]:
    first_error: LLMInvalidJSONError | None = None
    last_error: LLMInvalidJSONError | None = None
    retry_system_prompt = AUD_PLAN_SCHEMA_RETRY_SYSTEM_PROMPT

    for attempt_index in range(2):
        system_prompt = None if attempt_index == 0 else retry_system_prompt
        try:
            enhanced_payload = llm_service.generate_json(
                prompt,
                system_prompt=system_prompt,
                schema_name="aud_plan_ai_enhancement",
            )
        except LLMInvalidJSONError as error:
            if first_error is None:
                first_error = error
            last_error = error
            retry_system_prompt = AUD_PLAN_JSON_RETRY_SYSTEM_PROMPT
            continue

        try:
            return validate_and_normalize_ai_plan(enhanced_payload)
        except LLMInvalidJSONError as error:
            if first_error is None:
                first_error = error
            last_error = error
            retry_system_prompt = AUD_PLAN_SCHEMA_RETRY_SYSTEM_PROMPT
            continue

    assert last_error is not None
    if first_error is not last_error:
        raise last_error from first_error
    raise last_error


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
    normalized_enhanced_plan = generate_validated_enhanced_plan(
        resolved_llm_service,
        prompt,
    )
    updated_plan = dict(deterministic_plan)
    updated_plan["ai_enhanced_plan"] = normalized_enhanced_plan
    aud_plan.plan_json = json.dumps(updated_plan, indent=2, ensure_ascii=False)
    session.add(aud_plan)
    session.commit()
    session.refresh(aud_plan)
    return aud_plan

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import AUDPlan, EvidenceItem, SectionEvidencePack, SourceSummary
from app.services.aud_plan_ai_enhancement import parse_plan_json
from app.services.source_priority_service import build_source_priority_report

PRIMARY_ROLES = {"fdd", "supporting_doc"}
PPT_ROLES = {"kt_ppt"}
TRANSCRIPT_ROLES = {"kt_transcript", "kt_session"}
CONFIG_ROLES = {"config_workbook"}
TABLE_TYPES = {"table", "workbook_table", "document_ai_table"}
IMAGE_TYPES = {"image_reference", "slide"}
OPEN_ITEM_TYPES = {"open_item"}


@dataclass(frozen=True)
class PlanSection:
    section_id: str
    title: str
    source_roles: list[str]
    source_summary_ids: list[str]
    evidence_item_ids: list[str]


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def tokenize(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalize_text(value))
        if len(token) > 2
    }


def latest_aud_plan(session: Session, project_id: str) -> AUDPlan | None:
    return session.scalars(
        select(AUDPlan)
        .where(AUDPlan.project_id == project_id)
        .order_by(AUDPlan.updated_at.desc(), AUDPlan.created_at.desc())
    ).first()


def as_string_list(value: Any) -> list[str]:
    if value is None:
        return []

    if not isinstance(value, list):
        value = [value]

    return [str(item) for item in value if str(item).strip()]


def normalize_plan_sections(raw_sections: Any) -> list[PlanSection]:
    if not isinstance(raw_sections, list):
        return []

    sections: list[PlanSection] = []

    for index, section in enumerate(raw_sections, start=1):
        if not isinstance(section, dict):
            continue

        if section.get("include_in_aud") is False:
            continue

        title = str(section.get("title") or "").strip()
        if not title:
            continue

        section_id = str(section.get("section_id") or f"section-{index:03d}")
        sections.append(
            PlanSection(
                section_id=section_id,
                title=title,
                source_roles=as_string_list(
                    section.get("source_roles") or section.get("source_role_basis")
                ),
                source_summary_ids=as_string_list(section.get("source_summary_ids")),
                evidence_item_ids=as_string_list(section.get("evidence_item_ids")),
            )
        )

    return sections


def iter_plan_sections(plan_payload: dict[str, Any]) -> list[PlanSection]:
    ai_plan = plan_payload.get("ai_enhanced_plan")

    if isinstance(ai_plan, dict):
        ai_sections = normalize_plan_sections(ai_plan.get("sections"))
        if ai_sections:
            return ai_sections

    return normalize_plan_sections(plan_payload.get("sections"))


def parse_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def evidence_entry(evidence_item: EvidenceItem, reason: str) -> dict[str, Any]:
    return {
        "evidence_item_id": evidence_item.id,
        "source_uploaded_file_id": evidence_item.source_uploaded_file_id,
        "source_extracted_content_id": evidence_item.source_extracted_content_id,
        "evidence_type": evidence_item.evidence_type,
        "source_role": evidence_item.source_role,
        "title": evidence_item.title,
        "text": evidence_item.text,
        "priority": evidence_item.priority,
        "confidence": evidence_item.confidence,
        "reason": reason,
        "json_data": parse_json_object(evidence_item.json_data),
    }


def source_summary_entry(summary: SourceSummary) -> dict[str, Any]:
    return {
        "source_summary_id": summary.id,
        "source_uploaded_file_id": summary.source_uploaded_file_id,
        "source_role": summary.source_role,
        "summary_type": summary.summary_type,
        "summary_text": summary.summary_text,
        "summary_json": parse_json_object(summary.summary_json),
    }


def evidence_matches_section(section: PlanSection, evidence_item: EvidenceItem) -> bool:
    if evidence_item.id in section.evidence_item_ids:
        return True

    title_tokens = tokenize(section.title)
    if not title_tokens:
        return False

    evidence_tokens = tokenize(evidence_item.title) | tokenize(evidence_item.text)
    return bool(title_tokens & evidence_tokens)


def summary_matches_section(section: PlanSection, summary: SourceSummary) -> bool:
    if summary.id in section.source_summary_ids:
        return True

    if section.source_roles and summary.source_role in section.source_roles:
        return True

    title_tokens = tokenize(section.title)
    summary_tokens = tokenize(summary.summary_text) | tokenize(summary.summary_type)
    return bool(title_tokens & summary_tokens)


def add_unique_entry(
    bucket: list[dict[str, Any]],
    seen_ids: set[str],
    entry: dict[str, Any],
    id_key: str = "evidence_item_id",
) -> None:
    entry_id = str(entry.get(id_key) or "")
    if entry_id and entry_id in seen_ids:
        return

    if entry_id:
        seen_ids.add(entry_id)
    bucket.append(entry)


def add_evidence_to_pack(
    pack: dict[str, Any],
    evidence_item: EvidenceItem,
    *,
    reason: str,
    golden_source_present: bool,
    has_primary_source_context: bool,
    has_non_config_context: bool,
    seen_ids: set[str],
) -> None:
    entry = evidence_entry(evidence_item, reason)
    source_role = evidence_item.source_role or "unknown"
    evidence_type = evidence_item.evidence_type

    if source_role == "fdd":
        add_unique_entry(pack["primary_evidence"], seen_ids, entry)
        return

    if source_role in CONFIG_ROLES:
        if has_non_config_context:
            add_unique_entry(pack["configuration_evidence"], seen_ids, entry)
        else:
            entry["reason"] = (
                f"{reason}; promoted to primary because no FDD, PPT, or "
                "transcript evidence matched this section."
            )
            add_unique_entry(pack["primary_evidence"], seen_ids, entry)
        return

    if source_role in TRANSCRIPT_ROLES:
        add_unique_entry(pack["transcript_context"], seen_ids, entry)
        return

    if evidence_type in OPEN_ITEM_TYPES:
        add_unique_entry(pack["open_point_candidates"], seen_ids, entry)
        return

    if source_role in PPT_ROLES:
        if evidence_type in TABLE_TYPES:
            add_unique_entry(pack["table_candidates"], seen_ids, entry)
        elif evidence_type in IMAGE_TYPES:
            add_unique_entry(pack["image_candidates"], seen_ids, entry)
        else:
            add_unique_entry(pack["supporting_evidence"], seen_ids, entry)
        return

    if evidence_type in TABLE_TYPES:
        add_unique_entry(pack["table_candidates"], seen_ids, entry)
        return

    if evidence_type in IMAGE_TYPES:
        add_unique_entry(pack["image_candidates"], seen_ids, entry)
        return

    if golden_source_present and has_primary_source_context:
        entry["reason"] = (
            f"{reason}; retained as supporting because FDD evidence is primary."
        )
        add_unique_entry(pack["supporting_evidence"], seen_ids, entry)
        return

    if source_role in PRIMARY_ROLES:
        add_unique_entry(pack["primary_evidence"], seen_ids, entry)
        return

    add_unique_entry(pack["supporting_evidence"], seen_ids, entry)


def section_has_primary_context(matched_evidence: list[EvidenceItem]) -> bool:
    return any(item.source_role == "fdd" for item in matched_evidence)


def section_has_non_config_context(matched_evidence: list[EvidenceItem]) -> bool:
    return any(
        (item.source_role or "unknown")
        in {"fdd", "kt_ppt", "kt_transcript", "kt_session", "supporting_doc"}
        for item in matched_evidence
    )


def source_priority_rules(project_id: str, session: Session) -> tuple[list[str], bool]:
    report = build_source_priority_report(session, project_id)
    rules = [
        f"{item.source}: {item.rule}"
        for item in report.priority_order
    ]
    rules.extend(report.notes)
    return rules, bool(report.golden_source_files)


def empty_pack(
    section: PlanSection,
    *,
    priority_rules: list[str],
    golden_source_present: bool,
) -> dict[str, Any]:
    return {
        "section_id": section.section_id,
        "section_title": section.title,
        "source_priority_rules": priority_rules,
        "golden_source_present": golden_source_present,
        "primary_evidence": [],
        "supporting_evidence": [],
        "configuration_evidence": [],
        "transcript_context": [],
        "image_candidates": [],
        "table_candidates": [],
        "open_point_candidates": [],
        "excluded_evidence": [],
        "missing_information": [],
    }


def pack_char_count(pack: dict[str, Any]) -> int:
    return len(json.dumps(pack, ensure_ascii=False))


def trim_entry_text(entry: dict[str, Any], max_chars: int = 1200) -> None:
    text = entry.get("text")
    if isinstance(text, str) and len(text) > max_chars:
        entry["text"] = f"{text[:max_chars].rstrip()}..."

    summary_text = entry.get("summary_text")
    if isinstance(summary_text, str) and len(summary_text) > max_chars:
        entry["summary_text"] = f"{summary_text[:max_chars].rstrip()}..."


def enforce_pack_size(pack: dict[str, Any], max_chars: int) -> dict[str, Any]:
    if pack_char_count(pack) <= max_chars:
        return pack

    for bucket_name in (
        "primary_evidence",
        "supporting_evidence",
        "configuration_evidence",
        "transcript_context",
        "image_candidates",
        "table_candidates",
        "open_point_candidates",
        "excluded_evidence",
    ):
        for entry in pack[bucket_name]:
            trim_entry_text(entry)

    if pack_char_count(pack) <= max_chars:
        return pack

    for bucket_name in (
        "excluded_evidence",
        "supporting_evidence",
        "configuration_evidence",
        "transcript_context",
        "image_candidates",
        "table_candidates",
        "open_point_candidates",
        "primary_evidence",
    ):
        while pack[bucket_name] and pack_char_count(pack) > max_chars:
            removed_entry = pack[bucket_name].pop()
            if bucket_name == "excluded_evidence":
                continue

            pack["excluded_evidence"].append(
                {
                    "evidence_item_id": removed_entry.get("evidence_item_id"),
                    "source_role": removed_entry.get("source_role"),
                    "evidence_type": removed_entry.get("evidence_type"),
                    "title": removed_entry.get("title"),
                    "reason": "Excluded because section evidence pack size limit was reached.",
                }
            )

    if pack_char_count(pack) > max_chars:
        pack["source_priority_rules"] = pack["source_priority_rules"][:3]
        pack["missing_information"].append(
            "Pack was aggressively trimmed to stay within SECTION_EVIDENCE_MAX_CHARS."
        )

    return pack


def build_pack_for_section(
    *,
    section: PlanSection,
    evidence_items: list[EvidenceItem],
    source_summaries: list[SourceSummary],
    priority_rules: list[str],
    golden_source_present: bool,
    max_chars: int,
) -> dict[str, Any]:
    pack = empty_pack(
        section,
        priority_rules=priority_rules,
        golden_source_present=golden_source_present,
    )
    matched_evidence = [
        item for item in evidence_items if evidence_matches_section(section, item)
    ]
    matched_summaries = [
        summary for summary in source_summaries if summary_matches_section(section, summary)
    ]
    seen_ids: set[str] = set()
    has_fdd_context = section_has_primary_context(matched_evidence)
    has_non_config_context = section_has_non_config_context(matched_evidence)

    for evidence_item in sorted(
        matched_evidence,
        key=lambda item: (item.priority, item.created_at),
        reverse=True,
    ):
        add_evidence_to_pack(
            pack,
            evidence_item,
            reason="Matched section title or explicit AI plan mapping.",
            golden_source_present=golden_source_present,
            has_primary_source_context=has_fdd_context,
            has_non_config_context=has_non_config_context,
            seen_ids=seen_ids,
        )

    for summary in matched_summaries:
        entry = source_summary_entry(summary)
        if summary.source_role == "config_workbook":
            if has_non_config_context:
                pack["configuration_evidence"].append(entry)
            else:
                pack["primary_evidence"].append(entry)
        elif summary.source_role in TRANSCRIPT_ROLES:
            pack["transcript_context"].append(entry)
        elif summary.source_role == "fdd" and not pack["primary_evidence"]:
            pack["primary_evidence"].append(entry)
        else:
            pack["supporting_evidence"].append(entry)

    if not any(
        pack[bucket]
        for bucket in (
            "primary_evidence",
            "supporting_evidence",
            "configuration_evidence",
            "transcript_context",
            "image_candidates",
            "table_candidates",
        )
    ):
        pack["missing_information"].append(
            "No matching evidence found for this section."
        )

    return enforce_pack_size(pack, max_chars)


def build_section_evidence_packs(
    session: Session,
    project_id: str,
    settings: Settings | None = None,
) -> list[SectionEvidencePack]:
    resolved_settings = settings or get_settings()
    aud_plan = latest_aud_plan(session, project_id)
    if aud_plan is None:
        raise ValueError("AUD plan must exist before building section evidence packs.")

    plan_payload = parse_plan_json(aud_plan)
    sections = iter_plan_sections(plan_payload)
    if not sections:
        raise ValueError("AUD plan contains no sections for evidence pack building.")

    evidence_items = list(
        session.scalars(
            select(EvidenceItem)
            .where(EvidenceItem.project_id == project_id)
            .order_by(EvidenceItem.priority.desc(), EvidenceItem.created_at.asc())
        )
    )
    source_summaries = list(
        session.scalars(
            select(SourceSummary)
            .where(SourceSummary.project_id == project_id)
            .order_by(SourceSummary.source_role.asc(), SourceSummary.created_at.asc())
        )
    )
    priority_rules, golden_source_present = source_priority_rules(project_id, session)

    session.execute(
        delete(SectionEvidencePack).where(SectionEvidencePack.project_id == project_id)
    )
    packs: list[SectionEvidencePack] = []

    for section in sections:
        pack_payload = build_pack_for_section(
            section=section,
            evidence_items=evidence_items,
            source_summaries=source_summaries,
            priority_rules=priority_rules,
            golden_source_present=golden_source_present,
            max_chars=resolved_settings.SECTION_EVIDENCE_MAX_CHARS,
        )
        pack = SectionEvidencePack(
            project_id=project_id,
            section_id=section.section_id,
            section_title=section.title,
            pack_json=json.dumps(pack_payload, ensure_ascii=False),
        )
        session.add(pack)
        packs.append(pack)

    session.commit()

    for pack in packs:
        session.refresh(pack)

    return packs

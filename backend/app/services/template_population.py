from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.models import AUDSectionDraft, OpenPoint, Project

RAW_TEMPLATE_PLACEHOLDER_PATTERN = re.compile(r"<+[^<>]+>+")


@dataclass(frozen=True)
class VersionHistoryEntry:
    version: str
    date: date
    author: str
    reviewed_by: str = ""


@dataclass(frozen=True)
class PopulatedTable:
    title: str | None
    rows: list[list[str]]
    columns: list[str] = field(default_factory=list)
    source: str | None = None
    section_id: str | None = None
    style_hint: str = "standard"


@dataclass(frozen=True)
class PopulatedImage:
    storage_path: str
    slide_number: int | None = None
    slide_title: str | None = None
    caption: str | None = None


@dataclass(frozen=True)
class PopulatedSection:
    title: str
    paragraphs: list[str] = field(default_factory=list)
    tables: list[PopulatedTable] = field(default_factory=list)
    images: list[PopulatedImage] = field(default_factory=list)
    is_process: bool = False


@dataclass(frozen=True)
class PopulatedOpenPoint:
    topic: str
    question: str
    status: str


@dataclass(frozen=True)
class PopulatedDocumentModel:
    selected_template_path: Path
    customer_name: str
    module_name: str
    generated_date: date
    author_name: str
    version_history: VersionHistoryEntry
    purpose_scope: PopulatedSection
    sections: list[PopulatedSection]
    open_points: list[PopulatedOpenPoint]

    @property
    def toc_titles(self) -> list[str]:
        titles = [
            "Document Version History",
            "Purpose and Scope",
            self.purpose_scope.title,
        ]
        titles.extend(section.title for section in self.sections)
        if self.open_points:
            titles.append("Open Points")

        deduped_titles: list[str] = []
        seen_titles: set[str] = set()
        for title in titles:
            normalized = normalize_title(title)
            if not normalized or normalized in seen_titles:
                continue
            seen_titles.add(normalized)
            deduped_titles.append(title)
        return deduped_titles


@dataclass(frozen=True)
class SectionPopulationInput:
    title: str
    paragraphs: list[str] = field(default_factory=list)
    tables: list[PopulatedTable] = field(default_factory=list)
    images: list[PopulatedImage] = field(default_factory=list)
    source_role_basis: str = "unknown"


def normalize_title(value: str | None) -> str:
    if not value:
        return ""

    return " ".join(value.strip().split()).lower()


def clean_template_text(value: str | None) -> str:
    if not value:
        return ""

    return RAW_TEMPLATE_PLACEHOLDER_PATTERN.sub("", value).strip()


def has_content(section: PopulatedSection | SectionPopulationInput) -> bool:
    return bool(section.paragraphs or section.tables or section.images)


def first_project_text(project: Project, field_names: tuple[str, ...]) -> str:
    for field_name in field_names:
        value = getattr(project, field_name, None)
        if isinstance(value, str) and clean_template_text(value):
            return clean_template_text(value)

    return ""


class TemplatePopulationService:
    def __init__(
        self,
        selected_template_path: Path,
        project: Project,
        final_plan: dict[str, Any],
        section_drafts: list[AUDSectionDraft],
        section_inputs: list[SectionPopulationInput],
        open_points: list[OpenPoint],
        generated_date: date,
    ) -> None:
        self.selected_template_path = selected_template_path
        self.project = project
        self.final_plan = final_plan
        self.section_drafts = section_drafts
        self.section_inputs = section_inputs
        self.open_points = open_points
        self.generated_date = generated_date

    def build_document_model(self) -> PopulatedDocumentModel:
        author_name = first_project_text(
            self.project,
            ("author_name", "author", "owner_name", "name"),
        )
        reviewer_name = first_project_text(
            self.project,
            ("reviewer_name", "reviewed_by", "reviewer"),
        )
        purpose_scope = self.build_purpose_scope_section()
        sections = self.build_sections()

        return PopulatedDocumentModel(
            selected_template_path=self.selected_template_path,
            customer_name=clean_template_text(self.project.customer_name),
            module_name=clean_template_text(self.project.module_name),
            generated_date=self.generated_date,
            author_name=author_name,
            version_history=VersionHistoryEntry(
                version="1.0",
                date=self.generated_date,
                author=author_name,
                reviewed_by=reviewer_name,
            ),
            purpose_scope=purpose_scope,
            sections=sections,
            open_points=[
                PopulatedOpenPoint(
                    topic=clean_template_text(open_point.topic),
                    question=clean_template_text(open_point.question),
                    status=clean_template_text(open_point.status),
                )
                for open_point in self.open_points
                if normalize_title(open_point.status) == "open"
                and open_point.source_type == "llm_enhanced"
            ],
        )

    def build_purpose_scope_section(self) -> PopulatedSection:
        draft_paragraphs = self.find_draft_paragraphs("Purpose and Scope")
        if draft_paragraphs:
            return PopulatedSection(
                title="Purpose and Scope",
                paragraphs=draft_paragraphs,
            )

        deterministic_purpose = (
            "This document describes the current understanding of the "
            f"{clean_template_text(self.project.module_name) or 'selected'} module "
            "based on validated source material provided for this project."
        )
        return PopulatedSection(
            title="Purpose and Scope",
            paragraphs=[deterministic_purpose],
        )

    def build_sections(self) -> list[PopulatedSection]:
        populated_sections: list[PopulatedSection] = []
        seen_titles: set[str] = {"purpose and scope"}

        for section_input in self.section_inputs:
            normalized_title = normalize_title(section_input.title)
            if (
                not normalized_title
                or normalized_title in seen_titles
                or self.should_omit_section(section_input)
            ):
                continue

            populated_section = PopulatedSection(
                title=clean_template_text(section_input.title),
                paragraphs=[
                    cleaned_item
                    for item in section_input.paragraphs
                    if (cleaned_item := clean_template_text(item))
                ],
                tables=section_input.tables,
                images=section_input.images,
                is_process=self.is_process_section(section_input.title),
            )
            if not has_content(populated_section):
                continue

            seen_titles.add(normalized_title)
            populated_sections.append(populated_section)

        return populated_sections

    def find_draft_paragraphs(self, title: str) -> list[str]:
        normalized_target = normalize_title(title)
        for draft in self.section_drafts:
            if normalize_title(draft.title) != normalized_target:
                continue

            paragraphs = [
                clean_template_text(paragraph)
                for paragraph in re.split(r"\n\s*\n", draft.draft_text or "")
            ]
            paragraphs = [paragraph for paragraph in paragraphs if paragraph]
            if paragraphs:
                return paragraphs

        return []

    def should_omit_section(self, section: SectionPopulationInput) -> bool:
        normalized_title = normalize_title(section.title)
        if normalized_title == "documents referred":
            return True

        if normalized_title in {"roles and functions", "legend", "glossary"}:
            return not has_content(section)

        if normalized_title in {
            "reporting",
            "reports",
            "ricew",
            "reporting/ricew",
            "reporting and ricew",
        }:
            return not has_content(section)

        return False

    def is_process_section(self, title: str) -> bool:
        normalized_title = normalize_title(title)
        return bool(
            normalized_title.startswith("process ")
            or " process" in normalized_title
            or "flow" in normalized_title
        )

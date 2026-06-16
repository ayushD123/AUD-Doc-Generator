from pydantic import BaseModel, Field


class SourceFileReference(BaseModel):
    uploaded_file_id: str
    original_filename: str
    source_role: str
    file_type: str | None = None
    extracted_content_ids: list[str] = Field(default_factory=list)


class SourcePriorityItem(BaseModel):
    source: str
    priority: int
    purpose: str
    rule: str


class SourcePriorityReport(BaseModel):
    has_explicit_template: bool
    golden_source_files: list[SourceFileReference]
    source_roles_present: list[str]
    priority_order: list[SourcePriorityItem]
    warnings: list[str]
    recommended_default_template_needed: bool
    notes: list[str]

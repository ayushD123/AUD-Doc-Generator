from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvidenceItemRead(BaseModel):
    id: str
    project_id: str
    source_uploaded_file_id: str | None
    source_extracted_content_id: str | None
    evidence_type: str
    source_role: str | None
    title: str | None
    text: str | None
    json_data: str | None
    priority: int
    confidence: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

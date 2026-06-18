from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AUDSectionDraftRead(BaseModel):
    id: str
    project_id: str
    section_id: str
    title: str
    draft_text: str
    draft_json: str | None
    confidence: str
    review_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

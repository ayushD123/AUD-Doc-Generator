from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SectionEvidencePackRead(BaseModel):
    id: str
    project_id: str
    section_id: str
    section_title: str
    pack_json: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

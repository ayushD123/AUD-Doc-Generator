from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OpenPointRead(BaseModel):
    id: str
    project_id: str
    topic: str
    question: str
    status: str
    source_file_id: str | None
    source_content_id: str | None
    evidence: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

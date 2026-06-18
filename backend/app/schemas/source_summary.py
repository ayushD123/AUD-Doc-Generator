from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceSummaryRead(BaseModel):
    id: str
    project_id: str
    source_uploaded_file_id: str | None
    source_role: str
    summary_type: str
    summary_text: str
    summary_json: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

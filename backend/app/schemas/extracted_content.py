from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExtractedContentRead(BaseModel):
    id: str
    project_id: str
    uploaded_file_id: str
    content_type: str
    title: str | None
    text_content: str | None
    json_content: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UploadedFileRead(BaseModel):
    id: str
    project_id: str
    original_filename: str
    file_type: str | None
    storage_path: str
    source_role: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

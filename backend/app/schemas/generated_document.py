from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GeneratedDocumentRead(BaseModel):
    id: str
    project_id: str
    filename: str
    storage_path: str
    document_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobCreate(BaseModel):
    job_type: str = Field(min_length=1, max_length=100)
    message: str | None = None


class GenerateDocxJobOptions(BaseModel):
    use_ai_drafts: bool = True
    include_draft_sections: bool = True
    include_images: bool = True
    include_open_points: bool = True


class JobRead(BaseModel):
    id: str
    project_id: str
    job_type: str
    status: str
    progress: int
    message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

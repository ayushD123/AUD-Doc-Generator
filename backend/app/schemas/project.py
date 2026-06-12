from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str | None = None
    email_id: str | None = None
    customer_name: str | None = None
    module_name: str | None = None


class ProjectRead(BaseModel):
    id: str
    name: str | None
    email_id: str | None
    customer_name: str | None
    module_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

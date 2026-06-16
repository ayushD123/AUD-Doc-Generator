from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AUDPlanRead(BaseModel):
    id: str
    project_id: str
    status: str
    plan_json: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

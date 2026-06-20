from pydantic import BaseModel, ConfigDict


class AUDGenerationStartRead(BaseModel):
    job_id: str
    status: str
    message: str


class AUDGenerationStatusRead(BaseModel):
    job_id: str
    status: str
    current_stage: str | None
    completed_stages: list[str]
    failed_stage: str | None
    warnings: list[str]
    final_document_id: str | None
    final_document_url: str | None
    error: str | None

    model_config = ConfigDict(from_attributes=True)

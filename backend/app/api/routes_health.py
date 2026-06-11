from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def read_health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.APP_NAME,
    }

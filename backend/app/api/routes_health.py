from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.db.session import database_engine_config, engine
from app.services.db_health import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def read_health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.APP_NAME,
    }


@router.get("/health/db")
def read_database_health() -> dict[str, str | bool]:
    settings = get_settings()
    return check_database_connection(
        engine=engine,
        provider=database_engine_config.provider,
        secrets=(settings.ORACLE_DB_PASSWORD, settings.ORACLE_DB_WALLET_PASSWORD),
    )

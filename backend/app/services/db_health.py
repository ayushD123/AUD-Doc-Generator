from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, get_settings
from app.core.database_url import (
    DatabaseEngineConfig,
    build_database_engine_config,
)


def check_database_connection(
    engine: Engine,
    provider: str,
    secrets: tuple[str | None, ...] = (),
) -> dict[str, Any]:
    statement = text("SELECT 1 FROM DUAL" if engine.dialect.name == "oracle" else "SELECT 1")
    try:
        with engine.connect() as connection:
            connection.execute(statement).scalar_one()
    except SQLAlchemyError as exc:
        return {
            "status": "error",
            "db_provider": provider,
            "database_dialect": engine.dialect.name,
            "can_connect": False,
            "message": _safe_error_message(exc, secrets),
        }

    return {
        "status": "ok",
        "db_provider": provider,
        "database_dialect": engine.dialect.name,
        "can_connect": True,
        "message": "Database connection check succeeded.",
    }


def build_connection_diagnostics(
    settings: Settings | None = None,
) -> tuple[DatabaseEngineConfig, dict[str, Any]]:
    resolved_settings = settings or get_settings()
    database_config = build_database_engine_config(resolved_settings)
    diagnostics = {
        "provider": database_config.provider,
        "sanitized_url": database_config.safe_url,
        "dsn": _dsn_for_display(resolved_settings, database_config),
        "wallet_dir_exists": _wallet_dir_exists(resolved_settings),
    }
    return database_config, diagnostics


def create_health_check_engine(database_config: DatabaseEngineConfig) -> Engine:
    return create_engine(
        database_config.url,
        connect_args=database_config.connect_args,
        **database_config.engine_args,
    )


def _dsn_for_display(
    settings: Settings,
    database_config: DatabaseEngineConfig,
) -> str | None:
    if database_config.provider == "oracle":
        return settings.ORACLE_DB_DSN

    url = database_config.url
    if isinstance(url, str) and url.startswith("sqlite"):
        return url

    return None


def _wallet_dir_exists(settings: Settings) -> bool:
    if not settings.ORACLE_DB_WALLET_DIR:
        return False

    return Path(settings.ORACLE_DB_WALLET_DIR).is_dir()


def _safe_error_message(
    exc: SQLAlchemyError,
    secrets: tuple[str | None, ...],
) -> str:
    message = str(exc)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "***")

    return message[:500]

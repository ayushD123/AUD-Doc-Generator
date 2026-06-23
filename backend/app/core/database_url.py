import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.engine import URL, make_url

from app.core.config import Settings

logger = logging.getLogger(__name__)

SQLITE_DATABASE_URL = "sqlite:///./aud_generator.db"


class DatabaseConfigError(ValueError):
    """Raised when database environment settings are incomplete or invalid."""


@dataclass(frozen=True)
class DatabaseEngineConfig:
    provider: str
    url: str | URL
    connect_args: dict[str, Any] = field(default_factory=dict)
    engine_args: dict[str, Any] = field(default_factory=dict)

    @property
    def safe_url(self) -> str:
        if isinstance(self.url, URL):
            return self.url.render_as_string(hide_password=True)

        return make_url(self.url).render_as_string(hide_password=True)


def build_database_engine_config(settings: Settings) -> DatabaseEngineConfig:
    database_url = _blank_to_none(settings.DATABASE_URL)
    if database_url:
        provider = _provider_from_url(database_url)
        return DatabaseEngineConfig(
            provider=provider,
            url=database_url,
            connect_args=_connect_args_for_url(database_url, settings),
            engine_args=_engine_args_for_provider(provider, settings),
        )

    provider = settings.DB_PROVIDER.strip().lower()
    if provider == "sqlite":
        return DatabaseEngineConfig(
            provider="sqlite",
            url=SQLITE_DATABASE_URL,
            connect_args={"check_same_thread": False},
        )

    if provider == "oracle":
        return _build_oracle_engine_config(settings)

    raise DatabaseConfigError(
        "DB_PROVIDER must be 'sqlite' or 'oracle' when DATABASE_URL is not set."
    )


def log_database_startup(config: DatabaseEngineConfig) -> None:
    logger.info(
        "Database configured: provider=%s url=%s",
        config.provider,
        config.safe_url,
    )


def _build_oracle_engine_config(settings: Settings) -> DatabaseEngineConfig:
    missing = [
        name
        for name in ("ORACLE_DB_USER", "ORACLE_DB_PASSWORD", "ORACLE_DB_DSN")
        if not _blank_to_none(getattr(settings, name))
    ]
    if missing:
        raise DatabaseConfigError(
            "Missing required Oracle database settings: " + ", ".join(missing)
        )

    url = URL.create(
        "oracle+oracledb",
        username=settings.ORACLE_DB_USER,
        password=settings.ORACLE_DB_PASSWORD,
    )
    connect_args: dict[str, Any] = {
        "dsn": settings.ORACLE_DB_DSN,
    }
    wallet_dir = _blank_to_none(settings.ORACLE_DB_WALLET_DIR)
    if wallet_dir:
        connect_args["config_dir"] = wallet_dir

    wallet_password = _blank_to_none(settings.ORACLE_DB_WALLET_PASSWORD)
    if wallet_password:
        connect_args["wallet_password"] = wallet_password

    return DatabaseEngineConfig(
        provider="oracle",
        url=url,
        connect_args=connect_args,
        engine_args={
            "echo": settings.ORACLE_DB_ECHO,
            "pool_size": settings.ORACLE_DB_POOL_SIZE,
            "max_overflow": settings.ORACLE_DB_MAX_OVERFLOW,
            "pool_pre_ping": settings.ORACLE_DB_POOL_PRE_PING,
        },
    )


def _connect_args_for_url(
    database_url: str,
    settings: Settings,
) -> dict[str, Any]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}

    if database_url.startswith("oracle+oracledb"):
        connect_args: dict[str, Any] = {}
        wallet_dir = _blank_to_none(settings.ORACLE_DB_WALLET_DIR)
        if wallet_dir:
            connect_args["config_dir"] = wallet_dir

        wallet_password = _blank_to_none(settings.ORACLE_DB_WALLET_PASSWORD)
        if wallet_password:
            connect_args["wallet_password"] = wallet_password

        return connect_args

    return {}


def _engine_args_for_provider(provider: str, settings: Settings) -> dict[str, Any]:
    if provider != "oracle":
        return {}

    return {
        "echo": settings.ORACLE_DB_ECHO,
        "pool_size": settings.ORACLE_DB_POOL_SIZE,
        "max_overflow": settings.ORACLE_DB_MAX_OVERFLOW,
        "pool_pre_ping": settings.ORACLE_DB_POOL_PRE_PING,
    }


def _provider_from_url(database_url: str) -> str:
    if database_url.startswith("sqlite"):
        return "sqlite"

    if database_url.startswith("oracle"):
        return "oracle"

    return "custom"


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None

    stripped = value.strip()
    return stripped or None

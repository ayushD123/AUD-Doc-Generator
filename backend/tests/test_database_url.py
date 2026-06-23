import logging

import pytest

from app.core.config import Settings
from app.core.database_url import (
    SQLITE_DATABASE_URL,
    DatabaseConfigError,
    build_database_engine_config,
    log_database_startup,
)


def test_sqlite_url_remains_default() -> None:
    settings = Settings(_env_file=None)

    config = build_database_engine_config(settings)

    assert config.provider == "sqlite"
    assert config.url == SQLITE_DATABASE_URL
    assert config.connect_args == {"check_same_thread": False}
    assert config.engine_args == {}


def test_database_url_override_is_used_directly() -> None:
    settings = Settings(DATABASE_URL="sqlite:///./override.db", _env_file=None)

    config = build_database_engine_config(settings)

    assert config.provider == "sqlite"
    assert config.url == "sqlite:///./override.db"
    assert config.connect_args == {"check_same_thread": False}


def test_oracle_url_and_connection_args_are_constructed() -> None:
    settings = Settings(
        DB_PROVIDER="oracle",
        ORACLE_DB_USER="aud_user",
        ORACLE_DB_PASSWORD="secret-password",
        ORACLE_DB_DSN="adb_high",
        ORACLE_DB_WALLET_DIR="C:/wallets/aud",
        ORACLE_DB_WALLET_PASSWORD="wallet-secret",
        ORACLE_DB_ECHO=True,
        ORACLE_DB_POOL_SIZE=7,
        ORACLE_DB_MAX_OVERFLOW=3,
        ORACLE_DB_POOL_PRE_PING=False,
        _env_file=None,
    )

    config = build_database_engine_config(settings)

    assert config.provider == "oracle"
    assert config.url.drivername == "oracle+oracledb"
    assert config.url.username == "aud_user"
    assert config.url.password == "secret-password"
    assert config.connect_args == {
        "dsn": "adb_high",
        "config_dir": "C:/wallets/aud",
        "wallet_password": "wallet-secret",
    }
    assert config.engine_args == {
        "echo": True,
        "pool_size": 7,
        "max_overflow": 3,
        "pool_pre_ping": False,
    }


def test_oracle_logging_hides_password(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(
        DB_PROVIDER="oracle",
        ORACLE_DB_USER="aud_user",
        ORACLE_DB_PASSWORD="secret-password",
        ORACLE_DB_DSN="adb_high",
        _env_file=None,
    )
    config = build_database_engine_config(settings)

    caplog.set_level(logging.INFO, logger="app.core.database_url")
    log_database_startup(config)

    log_text = caplog.text
    assert "provider=oracle" in log_text
    assert "aud_user" in log_text
    assert "secret-password" not in log_text
    assert "***" in log_text


def test_missing_required_oracle_settings_raise_clear_error() -> None:
    settings = Settings(
        DB_PROVIDER="oracle",
        ORACLE_DB_USER="aud_user",
        _env_file=None,
    )

    with pytest.raises(DatabaseConfigError, match="ORACLE_DB_PASSWORD, ORACLE_DB_DSN"):
        build_database_engine_config(settings)

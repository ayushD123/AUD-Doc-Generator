from app.core.config import Settings, get_settings
from app.scripts.check_db_connection import main
from app.services.db_health import build_connection_diagnostics


def test_check_db_connection_cli_succeeds_for_sqlite(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    database_url = f"sqlite:///{(tmp_path / 'cli.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    try:
        exit_code = main()
    finally:
        get_settings.cache_clear()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "provider: sqlite" in output
    assert "dialect: sqlite" in output
    assert "can_connect: True" in output
    assert "password" not in output.lower()


def test_connection_diagnostics_do_not_expose_oracle_password() -> None:
    _, diagnostics = build_connection_diagnostics(
        settings=Settings(
            DB_PROVIDER="oracle",
            ORACLE_DB_USER="aud_user",
            ORACLE_DB_PASSWORD="secret-password",
            ORACLE_DB_DSN="adb_high",
            ORACLE_DB_WALLET_DIR="C:/not-a-real-wallet",
            _env_file=None,
        )
    )

    serialized = "\n".join(str(value) for value in diagnostics.values())
    assert diagnostics["provider"] == "oracle"
    assert diagnostics["dsn"] == "adb_high"
    assert diagnostics["wallet_dir_exists"] is False
    assert "secret-password" not in serialized
    assert "***" in diagnostics["sanitized_url"]

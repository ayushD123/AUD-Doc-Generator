from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.core.config import Settings, get_settings
from app.main import create_app


def _alembic_config():
    alembic_config = pytest.importorskip("alembic.config")
    return alembic_config.Config(str(Path("alembic.ini")))


def test_alembic_env_uses_app_database_settings(monkeypatch, tmp_path) -> None:
    command = pytest.importorskip("alembic.command")
    database_path = tmp_path / "alembic_env.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()

    try:
        command.upgrade(_alembic_config(), "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    inspector = inspect(engine)
    assert "projects" in inspector.get_table_names()


def test_sqlite_migration_runs_on_temporary_database(monkeypatch, tmp_path) -> None:
    command = pytest.importorskip("alembic.command")
    database_path = tmp_path / "migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()

    try:
        command.upgrade(_alembic_config(), "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert "alembic_version" in table_names
    assert {
        "projects",
        "uploaded_files",
        "jobs",
        "extracted_contents",
        "evidence_items",
        "source_summaries",
        "aud_plans",
        "aud_section_drafts",
        "section_evidence_packs",
        "open_points",
        "generated_documents",
        "aud_generation_runs",
    }.issubset(table_names)


def test_auto_create_tables_false_disables_startup_create(monkeypatch) -> None:
    called = False

    def fail_create_db_and_tables() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(AUTO_CREATE_TABLES=False, _env_file=None),
    )
    monkeypatch.setattr("app.main.create_db_and_tables", fail_create_db_and_tables)

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert called is False

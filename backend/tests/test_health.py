from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.main import create_app


def test_health_returns_ok() -> None:
    app = create_app(create_tables_on_startup=False)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "aud-generator-api",
    }


def test_database_health_returns_ok_for_sqlite(monkeypatch, tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'health.db').as_posix()}"
    test_engine = create_engine(database_url)
    monkeypatch.setattr("app.api.routes_health.engine", test_engine)
    monkeypatch.setattr(
        "app.api.routes_health.database_engine_config",
        SimpleNamespace(provider="sqlite"),
    )
    app = create_app(create_tables_on_startup=False)
    client = TestClient(app)

    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "db_provider": "sqlite",
        "database_dialect": "sqlite",
        "can_connect": True,
        "message": "Database connection check succeeded.",
    }

from fastapi.testclient import TestClient

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

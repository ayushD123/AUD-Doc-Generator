from fastapi.testclient import TestClient

from app.main import create_app


def test_health_allows_frontend_dev_origin() -> None:
    app = create_app(create_tables_on_startup=False)
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

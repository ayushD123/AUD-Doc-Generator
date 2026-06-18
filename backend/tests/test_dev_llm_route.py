from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


def test_dev_llm_endpoint_disabled_outside_development() -> None:
    app = create_app(create_tables_on_startup=False)
    app.dependency_overrides[get_settings] = lambda: Settings(
        ENVIRONMENT="production",
        LLM_PROVIDER="oci_responses",
        _env_file=None,
    )

    with TestClient(app) as client:
        response = client.post(
            "/dev/llm-test",
            json={"prompt": 'Reply with JSON only: {"status":"ok"}'},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Endpoint not found."

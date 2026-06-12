from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Job, Project, UploadedFile


@pytest.fixture()
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=engine)

    app = create_app(create_tables_on_startup=False)

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session_local() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_create_and_get_project(client: TestClient) -> None:
    create_response = client.post(
        "/projects",
        json={
            "name": "Asha Mehta",
            "email_id": "asha.mehta@example.com",
            "customer_name": "Vision Operations",
            "module_name": "Order Management",
        },
    )

    assert create_response.status_code == 201
    created_project = create_response.json()
    assert created_project["name"] == "Asha Mehta"
    assert created_project["email_id"] == "asha.mehta@example.com"
    assert created_project["customer_name"] == "Vision Operations"
    assert created_project["module_name"] == "Order Management"
    assert created_project["status"] == "draft"
    assert created_project["id"]
    assert created_project["created_at"]
    assert created_project["updated_at"]

    get_response = client.get(f"/projects/{created_project['id']}")

    assert get_response.status_code == 200
    assert get_response.json()["id"] == created_project["id"]


def test_list_projects(client: TestClient) -> None:
    client.post("/projects", json={"customer_name": "Customer A"})
    client.post("/projects", json={"customer_name": "Customer B"})

    response = client.get("/projects")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_create_and_list_project_jobs(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    create_response = client.post(
        f"/projects/{project_id}/jobs",
        json={
            "job_type": "aud_generation",
            "message": "Queued for local processing.",
        },
    )

    assert create_response.status_code == 201
    created_job = create_response.json()
    assert created_job["project_id"] == project_id
    assert created_job["job_type"] == "aud_generation"
    assert created_job["status"] == "pending"
    assert created_job["progress"] == 0
    assert created_job["message"] == "Queued for local processing."

    list_response = client.get(f"/projects/{project_id}/jobs")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == created_job["id"]


def test_create_job_returns_404_for_unknown_project(client: TestClient) -> None:
    response = client.post(
        "/projects/missing-project/jobs",
        json={"job_type": "aud_generation"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."

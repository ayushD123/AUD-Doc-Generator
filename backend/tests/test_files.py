from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.services.file_storage import LocalStorageService, get_file_storage


@pytest.fixture()
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    database_path = tmp_path / "test.db"
    storage_root = tmp_path / "storage"
    database_url = f"sqlite:///{database_path.as_posix()}"
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

    def override_file_storage() -> LocalStorageService:
        return LocalStorageService(storage_root)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_file_storage] = override_file_storage

    with TestClient(app) as test_client:
        test_client.storage_root = storage_root
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def create_project(client: TestClient) -> str:
    response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Order Management",
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def test_upload_accepted_file(client: TestClient) -> None:
    project_id = create_project(client)

    response = client.post(
        f"/projects/{project_id}/files",
        data={"source_role": "fdd"},
        files={
            "file": (
                "sample.docx",
                b"fake docx content",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 201
    uploaded_file = response.json()
    assert uploaded_file["project_id"] == project_id
    assert uploaded_file["original_filename"] == "sample.docx"
    assert uploaded_file["file_type"] == "docx"
    assert uploaded_file["source_role"] == "fdd"
    assert uploaded_file["storage_path"].startswith(f"projects/{project_id}/uploads/")
    assert uploaded_file["storage_path"].endswith(".docx")

    saved_file = client.storage_root / uploaded_file["storage_path"]
    assert saved_file.read_bytes() == b"fake docx content"


def test_upload_accepts_kt_session_mp4(client: TestClient) -> None:
    project_id = create_project(client)

    response = client.post(
        f"/projects/{project_id}/files",
        data={"source_role": "kt_session"},
        files={"file": ("session.mp4", b"fake mp4 content", "video/mp4")},
    )

    assert response.status_code == 201
    uploaded_file = response.json()
    assert uploaded_file["original_filename"] == "session.mp4"
    assert uploaded_file["file_type"] == "mp4"
    assert uploaded_file["source_role"] == "kt_session"


def test_upload_rejects_unsupported_file(client: TestClient) -> None:
    project_id = create_project(client)

    response = client.post(
        f"/projects/{project_id}/files",
        files={"file": ("sample.exe", b"not allowed", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]


def test_list_files(client: TestClient) -> None:
    project_id = create_project(client)
    client.post(
        f"/projects/{project_id}/files",
        data={"source_role": "supporting_doc"},
        files={"file": ("notes.txt", b"notes", "text/plain")},
    )

    response = client.get(f"/projects/{project_id}/files")

    assert response.status_code == 200
    files = response.json()
    assert len(files) == 1
    assert files[0]["original_filename"] == "notes.txt"
    assert files[0]["source_role"] == "supporting_doc"

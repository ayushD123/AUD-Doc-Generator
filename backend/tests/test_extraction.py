import json
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Job
from app.services.file_storage import LocalFileStorageService, get_file_storage
from app.workers.local_worker import process_extract_transcripts_job


@pytest.fixture()
def client_and_session(tmp_path: Path) -> Generator[tuple[TestClient, sessionmaker], None, None]:
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

    def override_file_storage() -> LocalFileStorageService:
        return LocalFileStorageService(storage_root)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_file_storage] = override_file_storage

    with TestClient(app) as test_client:
        test_client.storage_root = storage_root
        yield test_client, testing_session_local

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_extract_transcript_from_uploaded_txt(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
    transcript_text = "Welcome to the KT session.\nThis transcript is plain text."
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Order Management",
        },
    )
    project_id = project_response.json()["id"]

    upload_response = client.post(
        f"/projects/{project_id}/files",
        data={"source_role": "kt_transcript"},
        files={"file": ("kt-notes.txt", transcript_text.encode("utf-8"), "text/plain")},
    )
    assert upload_response.status_code == 201
    uploaded_file_id = upload_response.json()["id"]

    job_response = client.post(f"/projects/{project_id}/jobs/extract-transcripts")
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]

    with session_local() as session:
        job = session.scalar(select(Job).where(Job.id == job_id))
        assert job is not None
        process_extract_transcripts_job(
            session,
            job,
            sleep_seconds=0,
            storage_root=client.storage_root,
        )

    extracted_response = client.get(f"/projects/{project_id}/extracted-content")

    assert extracted_response.status_code == 200
    extracted_contents = extracted_response.json()
    assert len(extracted_contents) == 1
    extracted_content = extracted_contents[0]
    assert extracted_content["project_id"] == project_id
    assert extracted_content["uploaded_file_id"] == uploaded_file_id
    assert extracted_content["content_type"] == "transcript"
    assert extracted_content["title"] == "kt-notes.txt"
    assert extracted_content["text_content"] == transcript_text
    assert json.loads(extracted_content["json_content"]) == {
        "character_count": len(transcript_text),
        "word_count": len(transcript_text.split()),
    }

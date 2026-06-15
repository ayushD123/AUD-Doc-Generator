import json
from collections.abc import Generator
from io import BytesIO
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
from app.workers.local_worker import (
    process_extract_docx_job,
    process_extract_transcripts_job,
)


@pytest.fixture()
def client_and_session(
    tmp_path: Path,
) -> Generator[tuple[TestClient, sessionmaker], None, None]:
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


def create_docx_fixture() -> bytes:
    docx = pytest.importorskip("docx")
    document = docx.Document()
    document.add_heading("Order Management Overview", level=1)
    document.add_paragraph("Users create sales orders from imported demand.")

    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Field"
    table.cell(0, 1).text = "Value"
    table.cell(1, 0).text = "Source"
    table.cell(1, 1).text = "FDD"

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_extract_docx_from_uploaded_fdd(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
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
        data={"source_role": "fdd"},
        files={
            "file": (
                "order-management-fdd.docx",
                create_docx_fixture(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert upload_response.status_code == 201
    uploaded_file_id = upload_response.json()["id"]

    job_response = client.post(f"/projects/{project_id}/jobs/extract-docx")
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]

    with session_local() as session:
        job = session.scalar(select(Job).where(Job.id == job_id))
        assert job is not None
        process_extract_docx_job(
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
    assert extracted_content["content_type"] == "docx"
    assert extracted_content["title"] == "order-management-fdd.docx"
    assert "[Heading: Order Management Overview]" in extracted_content["text_content"]
    assert "Users create sales orders from imported demand." in extracted_content[
        "text_content"
    ]
    assert "Field | Value" in extracted_content["text_content"]
    assert "Source | FDD" in extracted_content["text_content"]

    json_content = json.loads(extracted_content["json_content"])
    assert json_content["source_role"] == "fdd"
    assert json_content["is_golden_source"] is True
    assert json_content["metadata"] == {
        "paragraph_count": 2,
        "table_count": 1,
        "heading_count": 1,
        "comment_count": 0,
    }
    assert json_content["headings"] == [
        {
            "index": 1,
            "text": "Order Management Overview",
            "style": "Heading 1",
            "level": 1,
        }
    ]
    assert json_content["tables"] == [
        {
            "index": 1,
            "rows": [["Field", "Value"], ["Source", "FDD"]],
        }
    ]

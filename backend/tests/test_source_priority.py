from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import ExtractedContent, UploadedFile


@pytest.fixture()
def client_and_session(
    tmp_path: Path,
) -> Generator[tuple[TestClient, sessionmaker], None, None]:
    database_path = tmp_path / "test.db"
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

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client, testing_session_local

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def add_uploaded_file(
    session: Session,
    project_id: str,
    filename: str,
    source_role: str,
    file_type: str,
) -> UploadedFile:
    uploaded_file = UploadedFile(
        project_id=project_id,
        original_filename=filename,
        file_type=file_type,
        storage_path=f"projects/{project_id}/uploads/{filename}",
        source_role=source_role,
    )
    session.add(uploaded_file)
    session.flush()
    return uploaded_file


def test_source_priority_report_marks_fdd_as_golden_source(
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

    with session_local() as session:
        fdd_file = add_uploaded_file(
            session,
            project_id,
            "order-management-fdd.docx",
            "fdd",
            "docx",
        )
        add_uploaded_file(session, project_id, "kt-flow.pptx", "kt_ppt", "pptx")
        add_uploaded_file(
            session,
            project_id,
            "kt-transcript.txt",
            "kt_transcript",
            "transcript_text",
        )
        add_uploaded_file(
            session,
            project_id,
            "configuration.xlsm",
            "config_workbook",
            "spreadsheet",
        )
        session.add(
            ExtractedContent(
                project_id=project_id,
                uploaded_file_id=fdd_file.id,
                content_type="docx",
                title=fdd_file.original_filename,
                text_content="FDD content",
                json_content='{"source_role": "fdd", "is_golden_source": true}',
            )
        )
        session.commit()

    response = client.get(f"/projects/{project_id}/source-priority-report")

    assert response.status_code == 200
    report = response.json()
    assert report["has_explicit_template"] is False
    assert report["source_roles_present"] == [
        "fdd",
        "kt_ppt",
        "kt_transcript",
        "config_workbook",
    ]
    assert len(report["golden_source_files"]) == 1
    golden_source_file = report["golden_source_files"][0]
    assert golden_source_file["uploaded_file_id"] == fdd_file.id
    assert golden_source_file["original_filename"] == "order-management-fdd.docx"
    assert golden_source_file["source_role"] == "fdd"
    assert golden_source_file["file_type"] == "docx"
    assert len(golden_source_file["extracted_content_ids"]) == 1
    priority_sources = [item["source"] for item in report["priority_order"]]
    assert priority_sources[:2] == ["default_scm_template", "fdd"]
    assert any("FDD is present" in note for note in report["notes"])


def test_source_priority_report_recommends_default_template_when_none_uploaded(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    with session_local() as session:
        add_uploaded_file(
            session,
            project_id,
            "supporting-notes.docx",
            "supporting_doc",
            "docx",
        )
        session.commit()

    response = client.get(f"/projects/{project_id}/source-priority-report")

    assert response.status_code == 200
    report = response.json()
    assert report["has_explicit_template"] is False
    assert report["recommended_default_template_needed"] is True
    assert report["priority_order"][0]["source"] == "default_scm_template"
    assert any("default SCM AUD template" in note for note in report["notes"])


def test_source_priority_report_returns_404_for_unknown_project(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, _ = client_and_session

    response = client.get("/projects/missing-project/source-priority-report")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."

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
from app.models import ExtractedContent, Job, OpenPoint, UploadedFile
from app.services.job_queue import LocalJobQueueService, get_job_queue_service
from app.workers.local_worker import process_extract_open_points_job


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
    app.dependency_overrides[get_job_queue_service] = LocalJobQueueService

    with TestClient(app) as test_client:
        yield test_client, testing_session_local

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
    return response.json()["id"]


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


def add_extracted_content(
    session: Session,
    project_id: str,
    uploaded_file: UploadedFile,
    content_type: str,
    text_content: str,
    json_content: dict | None = None,
) -> ExtractedContent:
    extracted_content = ExtractedContent(
        project_id=project_id,
        uploaded_file_id=uploaded_file.id,
        content_type=content_type,
        title=uploaded_file.original_filename,
        text_content=text_content,
        json_content=json.dumps(
            json_content or {"source_role": uploaded_file.source_role}
        ),
    )
    session.add(extracted_content)
    session.flush()
    return extracted_content


def process_open_points_job(
    client: TestClient,
    session_local: sessionmaker,
    project_id: str,
) -> list[dict]:
    job_response = client.post(f"/projects/{project_id}/jobs/extract-open-points")
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]

    with session_local() as session:
        job = session.scalar(select(Job).where(Job.id == job_id))
        assert job is not None
        process_extract_open_points_job(session, job, sleep_seconds=0)
        session.refresh(job)
        assert job.status == "completed"
        assert job.progress == 100

    response = client.get(f"/projects/{project_id}/open-points")
    assert response.status_code == 200
    return response.json()


def test_resolved_open_item_is_excluded(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
    project_id = create_project(client)

    with session_local() as session:
        fdd_file = add_uploaded_file(session, project_id, "fdd.docx", "fdd", "docx")
        add_extracted_content(
            session,
            project_id,
            fdd_file,
            "docx",
            "Open Points\nTax setup question - Status: Resolved",
        )
        session.commit()

    open_points = process_open_points_job(client, session_local, project_id)

    assert open_points == []


def test_needs_more_discussion_is_included(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
    project_id = create_project(client)

    with session_local() as session:
        support_file = add_uploaded_file(
            session,
            project_id,
            "supporting-notes.docx",
            "supporting_doc",
            "docx",
        )
        add_extracted_content(
            session,
            project_id,
            support_file,
            "docx",
            "Pricing approval flow needs more discussion with business.",
        )
        session.commit()

    open_points = process_open_points_job(client, session_local, project_id)

    assert len(open_points) == 1
    assert open_points[0]["topic"] == "Open Item"
    assert "needs more discussion" in open_points[0]["question"]
    assert open_points[0]["source_file_id"] == support_file.id
    assert open_points[0]["status"] == "Open"


def test_fdd_open_comment_is_included(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
    project_id = create_project(client)

    with session_local() as session:
        fdd_file = add_uploaded_file(session, project_id, "fdd.docx", "fdd", "docx")
        add_extracted_content(
            session,
            project_id,
            fdd_file,
            "docx",
            "Order capture is documented.",
            {
                "source_role": "fdd",
                "comments": [
                    {
                        "text": "Credit check behavior is TBD and awaiting confirmation.",
                    }
                ],
            },
        )
        session.commit()

    open_points = process_open_points_job(client, session_local, project_id)

    assert len(open_points) == 1
    assert open_points[0]["topic"] == "FDD Comment"
    assert "awaiting confirmation" in open_points[0]["question"]
    assert open_points[0]["source_file_id"] == fdd_file.id


def test_transcript_deferred_session_is_included(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
    project_id = create_project(client)

    with session_local() as session:
        transcript_file = add_uploaded_file(
            session,
            project_id,
            "kt-transcript.txt",
            "kt_transcript",
            "transcript_text",
        )
        add_extracted_content(
            session,
            project_id,
            transcript_file,
            "transcript",
            "We need another session with the fulfillment team to confirm with operations.",
        )
        session.commit()

    open_points = process_open_points_job(client, session_local, project_id)

    assert len(open_points) == 1
    assert "another session" in open_points[0]["question"]
    assert open_points[0]["source_content_id"] is not None


def test_non_fdd_conflict_excluded_when_fdd_is_clear(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
    project_id = create_project(client)

    with session_local() as session:
        fdd_file = add_uploaded_file(session, project_id, "fdd.docx", "fdd", "docx")
        ppt_file = add_uploaded_file(session, project_id, "deck.pptx", "kt_ppt", "pptx")
        add_extracted_content(
            session,
            project_id,
            fdd_file,
            "docx",
            "The FDD clearly states approvals are required for all returns.",
        )
        add_extracted_content(
            session,
            project_id,
            ppt_file,
            "pptx",
            "PPT conflict with FDD is pending confirmation.",
            {"source_role": "kt_ppt"},
        )
        session.commit()

    open_points = process_open_points_job(client, session_local, project_id)

    assert open_points == []


def test_non_fdd_conflict_included_when_fdd_absent(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
    project_id = create_project(client)

    with session_local() as session:
        ppt_file = add_uploaded_file(session, project_id, "deck.pptx", "kt_ppt", "pptx")
        add_extracted_content(
            session,
            project_id,
            ppt_file,
            "pptx",
            "PPT and workbook conflict; approval setup is pending confirmation.",
            {"source_role": "kt_ppt"},
        )
        session.commit()

    open_points = process_open_points_job(client, session_local, project_id)

    assert len(open_points) == 1
    assert "conflict" in open_points[0]["question"]


def test_refined_open_point_route_returns_evidence_text_not_metadata_json(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
    project_id = create_project(client)

    with session_local() as session:
        session.add(
            OpenPoint(
                project_id=project_id,
                topic="Shipping",
                question="Confirm shipping cutover timing.",
                status="Open",
                evidence=json.dumps(
                    {
                        "refinement_job_type": "refine_open_points_ai",
                        "evidence_text": "Original deterministic extraction.",
                        "source_open_point_ids": ["source-open-point-id"],
                        "evidence_item_ids": ["evidence-item-id"],
                        "reason": "Cleaned duplicate wording.",
                        "metadata": {"candidate_count": 1},
                    }
                ),
            )
        )
        session.commit()

    response = client.get(f"/projects/{project_id}/open-points")

    assert response.status_code == 200
    open_points = response.json()
    assert len(open_points) == 1
    assert open_points[0]["evidence"] == "Original deterministic extraction."
    assert open_points[0]["refinement_metadata"]["source_open_point_ids"] == [
        "source-open-point-id"
    ]
    assert "evidence_text" not in open_points[0]["refinement_metadata"]

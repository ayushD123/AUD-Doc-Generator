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
from app.models import ExtractedContent, Job, UploadedFile
from app.services.job_queue import LocalJobQueueService, get_job_queue_service
from app.workers.local_worker import process_generate_aud_plan_job


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
    json_content: dict,
    text_content: str = "",
) -> ExtractedContent:
    extracted_content = ExtractedContent(
        project_id=project_id,
        uploaded_file_id=uploaded_file.id,
        content_type=content_type,
        title=uploaded_file.original_filename,
        text_content=text_content,
        json_content=json.dumps(json_content),
    )
    session.add(extracted_content)
    session.flush()
    return extracted_content


def process_plan_job(
    client: TestClient,
    session_local: sessionmaker,
    project_id: str,
) -> dict:
    job_response = client.post(f"/projects/{project_id}/jobs/generate-aud-plan")
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]

    with session_local() as session:
        job = session.scalar(select(Job).where(Job.id == job_id))
        assert job is not None
        process_generate_aud_plan_job(session, job, sleep_seconds=0)
        session.refresh(job)
        assert job.status == "completed"
        assert job.progress == 100

    plan_response = client.get(f"/projects/{project_id}/aud-plan")
    assert plan_response.status_code == 200
    return json.loads(plan_response.json()["plan_json"])


def test_generate_aud_plan_uses_fdd_headings(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
    project_id = create_project(client)

    with session_local() as session:
        fdd_file = add_uploaded_file(
            session,
            project_id,
            "order-management-fdd.docx",
            "fdd",
            "docx",
        )
        add_extracted_content(
            session,
            project_id,
            fdd_file,
            "docx",
            {
                "source_role": "fdd",
                "is_golden_source": True,
                "headings": [
                    {"text": "Order Capture", "level": 1},
                    {"text": "Fulfillment Flow", "level": 1},
                ],
            },
        )
        session.commit()

    plan = process_plan_job(client, session_local, project_id)
    section_titles = [section["title"] for section in plan["sections"]]

    assert plan["generation_basis"] == "fdd_headings"
    assert plan["default_template_required"] is True
    assert section_titles == [
        "Cover Page",
        "Document Version History",
        "Table of Contents",
        "Enterprise Structure",
        "Order Capture",
        "Fulfillment Flow",
        "Open Points",
    ]
    enterprise_structure = plan["sections"][3]
    assert enterprise_structure["source_role_basis"] == "required_placeholder"
    order_capture = plan["sections"][4]
    assert order_capture["source_file_ids"] == [fdd_file.id]
    assert order_capture["source_role_basis"] == "fdd"
    assert order_capture["confidence"] == "high"
    assert order_capture["include_in_aud"] is True


def test_generate_aud_plan_adds_non_duplicate_ppt_sections_with_fdd(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
    project_id = create_project(client)

    with session_local() as session:
        fdd_file = add_uploaded_file(
            session,
            project_id,
            "order-management-fdd.docx",
            "fdd",
            "docx",
        )
        ppt_file = add_uploaded_file(
            session,
            project_id,
            "order-management-kt.pptx",
            "kt_ppt",
            "pptx",
        )
        add_extracted_content(
            session,
            project_id,
            fdd_file,
            "docx",
            {
                "source_role": "fdd",
                "is_golden_source": True,
                "headings": [
                    {"text": "Order Capture", "level": 1},
                    {"text": "Order and Quote Confirmation Reports", "level": 1},
                ],
            },
        )
        add_extracted_content(
            session,
            project_id,
            ppt_file,
            "pptx",
            {
                "source_role": "kt_ppt",
                "slides": [
                    {
                        "slide_number": 1,
                        "title": "Order Capture",
                        "texts": ["Duplicate PPT section should not override FDD."],
                    },
                    {
                        "slide_number": 2,
                        "title": "Order and Quote Confirmation Print Logic",
                        "texts": ["Similar to the FDD report heading."],
                    },
                    {
                        "slide_number": 3,
                        "title": "Pricing Assignments",
                        "texts": ["Supporting PPT-only configuration section."],
                    },
                ],
            },
        )
        session.commit()

    plan = process_plan_job(client, session_local, project_id)
    section_titles = [section["title"] for section in plan["sections"]]

    assert plan["generation_basis"] == "fdd_headings_with_ppt_support"
    assert section_titles == [
        "Cover Page",
        "Document Version History",
        "Table of Contents",
        "Enterprise Structure",
        "Order Capture",
        "Order and Quote Confirmation Reports",
        "Pricing Assignments",
        "Open Points",
    ]
    pricing_assignments = next(
        section for section in plan["sections"] if section["title"] == "Pricing Assignments"
    )
    assert pricing_assignments["source_file_ids"] == [ppt_file.id]
    assert pricing_assignments["source_role_basis"] == "kt_ppt"
    assert pricing_assignments["confidence"] == "medium"


def test_generate_aud_plan_detects_enterprise_structure_from_fdd_text(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
    project_id = create_project(client)

    with session_local() as session:
        fdd_file = add_uploaded_file(
            session,
            project_id,
            "order-management-fdd.docx",
            "fdd",
            "docx",
        )
        add_extracted_content(
            session,
            project_id,
            fdd_file,
            "docx",
            {
                "source_role": "fdd",
                "is_golden_source": True,
                "headings": [{"text": "Introduction", "level": 1}],
            },
            text_content=(
                "[Heading: Introduction]\n\n"
                "Introductory content.\n\n"
                "Enterprise Structure\n\n"
                "Business Unit: IT_BLCM_EUR_BU\n\n"
                "[Heading: Order Management]\n\n"
                "Order content."
            ),
        )
        session.commit()

    plan = process_plan_job(client, session_local, project_id)
    section_titles = [section["title"] for section in plan["sections"]]
    enterprise_structure = next(
        section for section in plan["sections"] if section["title"] == "Enterprise Structure"
    )

    assert section_titles[3:5] == ["Introduction", "Enterprise Structure"]
    assert enterprise_structure["source_content_ids"]
    assert enterprise_structure["source_role_basis"] == "fdd"
    assert enterprise_structure["confidence"] == "high"


def test_generate_aud_plan_uses_ppt_slide_titles_without_fdd(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session
    project_id = create_project(client)

    with session_local() as session:
        ppt_file = add_uploaded_file(
            session,
            project_id,
            "order-flow.pptx",
            "unknown",
            "pptx",
        )
        add_extracted_content(
            session,
            project_id,
            ppt_file,
            "pptx",
            {
                "source_role": "unknown",
                "slides": [
                    {"slide_number": 1, "title": "Welcome"},
                    {"slide_number": 2, "title": "Agenda"},
                    {
                        "slide_number": 3,
                        "title": "Huber OM KT Session",
                        "texts": ["Orchestration Processes and Order Types"],
                    },
                    {
                        "slide_number": 4,
                        "title": "Fulfillment Flow",
                        "texts": ["Reserve inventory and release shipment."],
                    },
                    {
                        "slide_number": 5,
                        "title": "Shipping Confirmation",
                        "image_count": 1,
                    },
                    {
                        "slide_number": 6,
                        "title": "Blank Divider",
                        "texts": [],
                        "image_count": 0,
                    },
                    {"slide_number": 7, "title": "Thank You"},
                ],
            },
        )
        session.commit()

    plan = process_plan_job(client, session_local, project_id)
    section_titles = [section["title"] for section in plan["sections"]]

    assert plan["generation_basis"] == "ppt_slide_titles"
    assert "Enterprise Structure" in section_titles
    assert "Fulfillment Flow" in section_titles
    assert "Shipping Confirmation" in section_titles
    assert "Welcome" not in section_titles
    assert "Agenda" not in section_titles
    assert "Huber OM KT Session" not in section_titles
    assert "Blank Divider" not in section_titles
    assert "Thank You" not in section_titles
    fulfillment_flow = next(
        section for section in plan["sections"] if section["title"] == "Fulfillment Flow"
    )
    assert fulfillment_flow["source_file_ids"] == [ppt_file.id]
    assert fulfillment_flow["source_role_basis"] == "kt_ppt"
    assert fulfillment_flow["confidence"] == "medium"


def test_generate_aud_plan_uses_generic_sections_for_transcript_only(
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
            {
                "source_role": "kt_transcript",
                "word_count": 120,
            },
            text_content="Presenter discussed the order management process.",
        )
        session.commit()

    plan = process_plan_job(client, session_local, project_id)
    section_titles = [section["title"] for section in plan["sections"]]

    assert plan["generation_basis"] == "transcript_generic_sections"
    assert section_titles == [
        "Cover Page",
        "Document Version History",
        "Table of Contents",
        "Introduction",
        "Enterprise Structure",
        "Purpose and Scope",
        "Process Overview",
        "Key Design Considerations",
        "Open Points",
    ]
    introduction = plan["sections"][3]
    assert introduction["source_file_ids"] == [transcript_file.id]
    assert introduction["source_role_basis"] == "kt_transcript"
    assert introduction["confidence"] == "low"

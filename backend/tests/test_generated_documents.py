import json
from base64 import b64decode
from collections.abc import Generator
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.api.routes_generated_documents as generated_document_routes
import app.services.docx_generation as docx_generation
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import (
    AUDPlan,
    ExtractedContent,
    GeneratedDocument,
    Job,
    OpenPoint,
    UploadedFile,
)
from app.workers.local_worker import process_generate_docx_job

ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture()
def client_session_and_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, sessionmaker, Path], None, None]:
    database_path = tmp_path / "test.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    storage_root = tmp_path / "storage"
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(docx_generation, "get_local_storage_root", lambda: storage_root)
    monkeypatch.setattr(
        generated_document_routes,
        "get_local_storage_root",
        lambda: storage_root,
    )

    app = create_app(create_tables_on_startup=False)

    def override_get_db() -> Generator[Session, None, None]:
        with testing_session_local() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client, testing_session_local, storage_root

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def create_project(client: TestClient) -> str:
    response = client.post(
        "/projects",
        json={
            "name": "Asha Mehta",
            "customer_name": "Vision Operations",
            "module_name": "Order Management",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def add_project_generation_inputs(session: Session, project_id: str) -> None:
    uploaded_file = UploadedFile(
        project_id=project_id,
        original_filename="order-management-fdd.docx",
        file_type="docx",
        storage_path=f"projects/{project_id}/uploads/order-management-fdd.docx",
        source_role="fdd",
    )
    session.add(uploaded_file)
    session.flush()

    extracted_content = ExtractedContent(
        project_id=project_id,
        uploaded_file_id=uploaded_file.id,
        content_type="docx",
        title=uploaded_file.original_filename,
        text_content=(
            "[Heading: Order Capture]\n\n"
            "Orders are captured from validated FDD source material before fulfillment.\n\n"
            "[Heading: Fulfillment Flow]\n\n"
            "Fulfillment processing is documented separately."
        ),
        json_content=json.dumps(
            {
                "source_role": "fdd",
                "is_golden_source": True,
                "headings": [{"text": "Order Capture", "level": 1}],
            }
        ),
    )
    session.add(extracted_content)
    session.flush()

    plan_payload = {
        "sections": [
            {"title": "Cover Page", "include_in_aud": True},
            {"title": "Document Version History", "include_in_aud": True},
            {
                "title": "Order Capture",
                "include_in_aud": True,
                "source_role_basis": "fdd",
                "source_content_ids": [extracted_content.id],
            },
            {"title": "Open Points", "include_in_aud": True},
        ],
    }
    session.add(
        AUDPlan(
            project_id=project_id,
            status="draft",
            plan_json=json.dumps(plan_payload),
        )
    )
    session.add(
        OpenPoint(
            project_id=project_id,
            topic="Open Item",
            question="Confirm order approval threshold.",
            status="Open",
        )
    )
    session.add(
        OpenPoint(
            project_id=project_id,
            topic="Closed Item",
            question="This resolved question should not appear.",
            status="Closed",
        )
    )
    session.commit()


def test_generate_docx_job_creates_file_and_generated_document_record(
    client_session_and_storage: tuple[TestClient, sessionmaker, Path],
) -> None:
    client, session_local, storage_root = client_session_and_storage
    project_id = create_project(client)

    with session_local() as session:
        add_project_generation_inputs(session, project_id)

    job_response = client.post(f"/projects/{project_id}/jobs/generate-docx")
    assert job_response.status_code == 201
    queued_job = job_response.json()
    assert queued_job["job_type"] == "generate_docx"
    assert queued_job["message"] == "DOCX generation job queued."

    with session_local() as session:
        job = session.scalar(select(Job).where(Job.id == queued_job["id"]))
        assert job is not None
        process_generate_docx_job(session, job, sleep_seconds=0)
        session.refresh(job)
        assert job.status == "completed"
        assert job.progress == 100

        generated_document = session.scalar(
            select(GeneratedDocument).where(GeneratedDocument.project_id == project_id)
        )
        assert generated_document is not None
        assert generated_document.document_type == "aud_docx"
        assert generated_document.filename.endswith(".docx")
        output_path = storage_root / generated_document.storage_path
        assert output_path.exists()

    document = Document(output_path)
    document_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Application Understanding Document" in document_text
    assert "Vision Operations" in document_text
    assert "Order Management" in document_text
    assert "Purpose and Scope" in document_text
    assert "Order Capture" in document_text
    assert (
        "Orders are captured from validated FDD source material before fulfillment."
        in document_text
    )
    assert "Draft generated for internal review." in document_text
    table_text = "\n".join(
        cell.text
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    )
    assert "Confirm order approval threshold." in table_text
    assert "This resolved question should not appear." not in table_text

    list_response = client.get(f"/projects/{project_id}/generated-documents")
    assert list_response.status_code == 200
    listed_documents = list_response.json()
    assert len(listed_documents) == 1

    download_response = client.get(
        f"/projects/{project_id}/generated-documents/{listed_documents[0]['id']}/download"
    )
    assert download_response.status_code == 200
    assert download_response.content.startswith(b"PK")


def test_missing_section_content_uses_placeholder(
    client_session_and_storage: tuple[TestClient, sessionmaker, Path],
) -> None:
    client, session_local, storage_root = client_session_and_storage
    project_id = create_project(client)

    with session_local() as session:
        uploaded_file = UploadedFile(
            project_id=project_id,
            original_filename="order-management-fdd.docx",
            file_type="docx",
            storage_path=f"projects/{project_id}/uploads/order-management-fdd.docx",
            source_role="fdd",
        )
        session.add(uploaded_file)
        session.flush()

        extracted_content = ExtractedContent(
            project_id=project_id,
            uploaded_file_id=uploaded_file.id,
            content_type="docx",
            title=uploaded_file.original_filename,
            text_content="[Heading: Available Section]\n\nAvailable FDD content.",
            json_content=json.dumps({"source_role": "fdd"}),
        )
        session.add(extracted_content)
        session.flush()
        session.add(
            AUDPlan(
                project_id=project_id,
                status="draft",
                plan_json=json.dumps(
                    {
                        "sections": [
                            {
                                "title": "Missing Section",
                                "include_in_aud": True,
                                "source_role_basis": "fdd",
                                "source_content_ids": [extracted_content.id],
                            }
                        ]
                    }
                ),
            )
        )
        session.commit()

    with session_local() as session:
        job = Job(project_id=project_id, job_type="generate_docx")
        session.add(job)
        session.commit()
        process_generate_docx_job(session, job, sleep_seconds=0)
        generated_document = session.scalar(
            select(GeneratedDocument).where(GeneratedDocument.project_id == project_id)
        )
        assert generated_document is not None
        output_path = storage_root / generated_document.storage_path

    document_text = "\n".join(
        paragraph.text for paragraph in Document(output_path).paragraphs
    )
    assert "Missing Section" in document_text
    assert "<Content not available in provided source material>" in document_text


def test_fdd_content_has_priority_when_mapped_with_ppt(
    client_session_and_storage: tuple[TestClient, sessionmaker, Path],
) -> None:
    client, session_local, storage_root = client_session_and_storage
    project_id = create_project(client)

    with session_local() as session:
        fdd_file = UploadedFile(
            project_id=project_id,
            original_filename="order-management-fdd.docx",
            file_type="docx",
            storage_path=f"projects/{project_id}/uploads/order-management-fdd.docx",
            source_role="fdd",
        )
        ppt_file = UploadedFile(
            project_id=project_id,
            original_filename="order-management-kt.pptx",
            file_type="pptx",
            storage_path=f"projects/{project_id}/uploads/order-management-kt.pptx",
            source_role="kt_ppt",
        )
        session.add_all([fdd_file, ppt_file])
        session.flush()

        fdd_content = ExtractedContent(
            project_id=project_id,
            uploaded_file_id=fdd_file.id,
            content_type="docx",
            title=fdd_file.original_filename,
            text_content=(
                "[Heading: Order Capture]\n\n"
                "FDD-approved order capture content wins for this section."
            ),
            json_content=json.dumps({"source_role": "fdd", "is_golden_source": True}),
        )
        ppt_content = ExtractedContent(
            project_id=project_id,
            uploaded_file_id=ppt_file.id,
            content_type="pptx",
            title=ppt_file.original_filename,
            text_content="Slide 1\nTitle: Order Capture\nText:\n- PPT-only order capture content.",
            json_content=json.dumps(
                {
                    "source_role": "kt_ppt",
                    "slides": [
                        {
                            "slide_number": 1,
                            "title": "Order Capture",
                            "texts": ["PPT-only order capture content."],
                            "tables": [],
                            "notes": None,
                        }
                    ],
                }
            ),
        )
        session.add_all([fdd_content, ppt_content])
        session.flush()
        session.add(
            AUDPlan(
                project_id=project_id,
                status="draft",
                plan_json=json.dumps(
                    {
                        "sections": [
                            {
                                "title": "Order Capture",
                                "include_in_aud": True,
                                "source_role_basis": "kt_ppt",
                                "source_content_ids": [ppt_content.id, fdd_content.id],
                            }
                        ]
                    }
                ),
            )
        )
        session.commit()

    with session_local() as session:
        job = Job(project_id=project_id, job_type="generate_docx")
        session.add(job)
        session.commit()
        process_generate_docx_job(session, job, sleep_seconds=0)
        generated_document = session.scalar(
            select(GeneratedDocument).where(GeneratedDocument.project_id == project_id)
        )
        assert generated_document is not None
        output_path = storage_root / generated_document.storage_path

    document_text = "\n".join(
        paragraph.text for paragraph in Document(output_path).paragraphs
    )
    assert "FDD-approved order capture content wins for this section." in document_text
    assert "PPT-only order capture content." not in document_text


def test_stale_standard_plan_is_refreshed_before_docx_generation(
    client_session_and_storage: tuple[TestClient, sessionmaker, Path],
) -> None:
    client, session_local, storage_root = client_session_and_storage
    project_id = create_project(client)

    with session_local() as session:
        fdd_file = UploadedFile(
            project_id=project_id,
            original_filename="fdd.docx",
            file_type="docx",
            storage_path=f"projects/{project_id}/uploads/fdd.docx",
            source_role="fdd",
        )
        session.add(fdd_file)
        session.flush()

        session.add(
            ExtractedContent(
                project_id=project_id,
                uploaded_file_id=fdd_file.id,
                content_type="docx",
                title=fdd_file.original_filename,
                text_content=(
                    "[Heading: Topical Essay]\n\n"
                    "The FDD topical essay content should appear after plan refresh."
                ),
                json_content=json.dumps(
                    {
                        "source_role": "fdd",
                        "is_golden_source": True,
                        "headings": [{"text": "Topical Essay", "level": 2}],
                    }
                ),
            )
        )
        session.add(
            AUDPlan(
                project_id=project_id,
                status="draft",
                plan_json=json.dumps(
                    {
                        "generation_basis": "standard_sections_only",
                        "sections": [
                            {"title": "Cover Page", "include_in_aud": True},
                            {
                                "title": "Document Version History",
                                "include_in_aud": True,
                            },
                            {"title": "Table of Contents", "include_in_aud": True},
                            {"title": "Open Points", "include_in_aud": True},
                        ],
                    }
                ),
            )
        )
        session.commit()

    with session_local() as session:
        job = Job(project_id=project_id, job_type="generate_docx")
        session.add(job)
        session.commit()
        process_generate_docx_job(session, job, sleep_seconds=0)
        generated_document = session.scalar(
            select(GeneratedDocument).where(GeneratedDocument.project_id == project_id)
        )
        assert generated_document is not None
        output_path = storage_root / generated_document.storage_path
        refreshed_plans = session.scalars(
            select(AUDPlan).where(AUDPlan.project_id == project_id)
        ).all()
        assert len(refreshed_plans) == 2

    document_text = "\n".join(
        paragraph.text for paragraph in Document(output_path).paragraphs
    )
    assert "Topical Essay" in document_text
    assert "The FDD topical essay content should appear after plan refresh." in document_text


def test_ppt_images_are_added_for_matching_section(
    client_session_and_storage: tuple[TestClient, sessionmaker, Path],
) -> None:
    client, session_local, storage_root = client_session_and_storage
    project_id = create_project(client)
    unsupported_image_storage_path = (
        f"projects/{project_id}/extracted_images/ppt-file/slide_001_image_001.wmf"
    )
    image_storage_path = f"projects/{project_id}/extracted_images/ppt-file/slide_001_image_001.png"
    low_value_image_storage_path = (
        f"projects/{project_id}/extracted_images/ppt-file/slide_002_image_001.png"
    )
    mapped_image_storage_path = (
        f"projects/{project_id}/extracted_images/ppt-file/slide_003_image_001.png"
    )
    unsupported_image_path = storage_root / unsupported_image_storage_path
    image_path = storage_root / image_storage_path
    low_value_image_path = storage_root / low_value_image_storage_path
    mapped_image_path = storage_root / mapped_image_storage_path
    image_path.parent.mkdir(parents=True, exist_ok=True)
    unsupported_image_path.write_bytes(b"unsupported-wmf")
    image_path.write_bytes(b64decode(ONE_PIXEL_PNG))
    low_value_image_path.write_bytes(b64decode(ONE_PIXEL_PNG))
    mapped_image_path.write_bytes(b64decode(ONE_PIXEL_PNG))

    with session_local() as session:
        ppt_file = UploadedFile(
            project_id=project_id,
            original_filename="order-flow.pptx",
            file_type="pptx",
            storage_path=f"projects/{project_id}/uploads/order-flow.pptx",
            source_role="unknown",
        )
        session.add(ppt_file)
        session.flush()

        ppt_content = ExtractedContent(
            project_id=project_id,
            uploaded_file_id=ppt_file.id,
            content_type="pptx",
            title=ppt_file.original_filename,
            text_content="Slide 1\nTitle: Fulfillment Flow",
            json_content=json.dumps(
                {
                    "source_role": "unknown",
                    "slides": [
                        {
                            "slide_number": 1,
                            "title": "Fulfillment Flow",
                            "texts": ["Reserve inventory and release shipment."],
                            "tables": [],
                            "notes": None,
                            "image_count": 2,
                            "image_paths": [
                                unsupported_image_storage_path,
                                image_storage_path,
                            ],
                        },
                        {
                            "slide_number": 2,
                            "title": "Thank You",
                            "texts": ["Thank You"],
                            "tables": [],
                            "notes": None,
                            "image_count": 1,
                            "image_paths": [low_value_image_storage_path],
                        },
                        {
                            "slide_number": 3,
                            "title": "Configuration Snapshot",
                            "texts": ["High-value screenshot with process labels."],
                            "tables": [],
                            "notes": None,
                            "image_count": 1,
                            "image_paths": [mapped_image_storage_path],
                        },
                    ],
                    "image_paths": [
                        unsupported_image_storage_path,
                        image_storage_path,
                        low_value_image_storage_path,
                        mapped_image_storage_path,
                    ],
                    "total_image_count": 4,
                }
            ),
        )
        session.add(ppt_content)
        session.flush()
        session.add(
            AUDPlan(
                project_id=project_id,
                status="draft",
                plan_json=json.dumps(
                    {
                        "sections": [
                            {
                                "title": "Fulfillment Flow",
                                "include_in_aud": True,
                                "source_role_basis": "kt_ppt",
                                "source_content_ids": [ppt_content.id],
                            },
                            {
                                "title": "Exception Handling",
                                "include_in_aud": True,
                                "source_role_basis": "kt_ppt",
                                "source_content_ids": [ppt_content.id],
                                "notes": ["Source slide 3."],
                            },
                        ]
                    }
                ),
            )
        )
        session.commit()

    with session_local() as session:
        job = Job(project_id=project_id, job_type="generate_docx")
        session.add(job)
        session.commit()
        process_generate_docx_job(session, job, sleep_seconds=0)
        generated_document = session.scalar(
            select(GeneratedDocument).where(GeneratedDocument.project_id == project_id)
        )
        assert generated_document is not None
        output_path = storage_root / generated_document.storage_path

    document = Document(output_path)
    document_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert len(document.inline_shapes) == 2
    assert "Source image from slide 1: Fulfillment Flow" in document_text
    assert "Source image from slide 3: Configuration Snapshot" in document_text
    assert "Source image from slide 2: Thank You" not in document_text


def test_list_generated_documents_returns_404_for_unknown_project(
    client_session_and_storage: tuple[TestClient, sessionmaker, Path],
) -> None:
    client, _, _ = client_session_and_storage

    response = client.get("/projects/missing-project/generated-documents")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."

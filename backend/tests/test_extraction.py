import json
from base64 import b64decode
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
from app.services.pptx_extraction import extract_pptx
from app.workers.local_worker import (
    process_extract_all_job,
    process_extract_docx_job,
    process_extract_pptx_job,
    process_extract_spreadsheets_job,
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


def create_pptx_fixture(tmp_path: Path) -> bytes:
    pptx = pytest.importorskip("pptx")
    pptx_util = pytest.importorskip("pptx.util")

    presentation = pptx.Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = "Fulfillment Flow"

    text_box = slide.shapes.add_textbox(
        pptx_util.Inches(1),
        pptx_util.Inches(1.4),
        pptx_util.Inches(6),
        pptx_util.Inches(0.8),
    )
    text_box.text_frame.text = "Reserve inventory and release shipment."

    table = slide.shapes.add_table(
        2,
        2,
        pptx_util.Inches(1),
        pptx_util.Inches(2.4),
        pptx_util.Inches(5),
        pptx_util.Inches(1),
    ).table
    table.cell(0, 0).text = "Step"
    table.cell(0, 1).text = "Owner"
    table.cell(1, 0).text = "Ship Confirm"
    table.cell(1, 1).text = "Warehouse"

    image_path = tmp_path / "sample.png"
    image_path.write_bytes(
        b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
            "AAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
    )
    slide.shapes.add_picture(
        str(image_path),
        pptx_util.Inches(6.4),
        pptx_util.Inches(1.3),
        width=pptx_util.Inches(1),
        height=pptx_util.Inches(1),
    )

    buffer = BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()


def test_extract_pptx_infers_title_from_top_text_box(tmp_path: Path) -> None:
    pptx = pytest.importorskip("pptx")
    pptx_util = pytest.importorskip("pptx.util")

    presentation = pptx.Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])

    title_box = slide.shapes.add_textbox(
        pptx_util.Inches(0.7),
        pptx_util.Inches(0.5),
        pptx_util.Inches(8),
        pptx_util.Inches(0.5),
    )
    title_box.text_frame.text = "Export Order Process"

    body_box = slide.shapes.add_textbox(
        pptx_util.Inches(0.7),
        pptx_util.Inches(1.5),
        pptx_util.Inches(8),
        pptx_util.Inches(1),
    )
    body_box.text_frame.text = "Create quotation and submit accepted order."

    footer_box = slide.shapes.add_textbox(
        pptx_util.Inches(0.7),
        pptx_util.Inches(6.9),
        pptx_util.Inches(5),
        pptx_util.Inches(0.3),
    )
    footer_box.text_frame.text = "Confidential - Oracle Restricted"

    page_number_box = slide.shapes.add_textbox(
        pptx_util.Inches(0.3),
        pptx_util.Inches(6.9),
        pptx_util.Inches(0.4),
        pptx_util.Inches(0.3),
    )
    page_number_box.text_frame.text = "3"

    pptx_path = tmp_path / "inferred-title.pptx"
    presentation.save(pptx_path)

    extracted = extract_pptx(
        pptx_path,
        tmp_path / "images",
        "projects/test/extracted_images/inferred-title",
    )
    slide_json = extracted["json_content"]["slides"][0]

    assert slide_json["title"] == "Export Order Process"
    assert slide_json["texts"] == ["Create quotation and submit accepted order."]
    assert "Title: Export Order Process" in extracted["text_content"]
    assert "Confidential" not in extracted["text_content"]


def test_extract_pptx_from_uploaded_kt_ppt(
    client_and_session: tuple[TestClient, sessionmaker],
    tmp_path: Path,
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
        data={"source_role": "kt_ppt"},
        files={
            "file": (
                "order-flow.pptx",
                create_pptx_fixture(tmp_path),
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )
    assert upload_response.status_code == 201
    uploaded_file_id = upload_response.json()["id"]

    job_response = client.post(f"/projects/{project_id}/jobs/extract-pptx")
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]

    with session_local() as session:
        job = session.scalar(select(Job).where(Job.id == job_id))
        assert job is not None
        process_extract_pptx_job(
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
    assert extracted_content["content_type"] == "pptx"
    assert extracted_content["title"] == "order-flow.pptx"
    assert "Slide 1" in extracted_content["text_content"]
    assert "Title: Fulfillment Flow" in extracted_content["text_content"]
    assert "Reserve inventory and release shipment." in extracted_content["text_content"]
    assert "Ship Confirm | Warehouse" in extracted_content["text_content"]
    assert "Images: 1" in extracted_content["text_content"]

    json_content = json.loads(extracted_content["json_content"])
    assert json_content["source_role"] == "kt_ppt"
    assert json_content["slide_count"] == 1
    assert json_content["table_count"] == 1
    assert json_content["total_image_count"] == 1
    assert len(json_content["image_paths"]) == 1
    assert json_content["slides"][0]["title"] == "Fulfillment Flow"
    assert json_content["slides"][0]["texts"] == [
        "Reserve inventory and release shipment.",
    ]
    assert json_content["slides"][0]["tables"] == [
        {
            "index": 1,
            "rows": [["Step", "Owner"], ["Ship Confirm", "Warehouse"]],
        }
    ]
    assert json_content["slides"][0]["image_count"] == 1
    assert json_content["slides"][0]["image_paths"] == json_content["image_paths"]

    saved_image_path = client.storage_root / json_content["image_paths"][0]
    assert saved_image_path.exists()
    assert saved_image_path.parent.name == uploaded_file_id


def create_workbook_fixture() -> bytes:
    openpyxl = pytest.importorskip("openpyxl")

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Configuration Values"
    worksheet.append(["Parameter", "Value", "Formula"])
    worksheet.append(["Enable ATP", "Yes", "=LEN(B2)"])
    worksheet.append(["Lead Time", 5, "=B3*2"])

    notes_sheet = workbook.create_sheet("Notes")
    notes_sheet.append(["Topic", "Detail"])
    notes_sheet.append(["Shipping", "Validate against FDD"])

    hidden_sheet = workbook.create_sheet("Hidden Setup")
    hidden_sheet.sheet_state = "hidden"
    hidden_sheet.append(["Should", "Not Extract"])

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_extract_spreadsheets_from_uploaded_xlsx_and_xlsm(
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
    workbook_content = create_workbook_fixture()

    xlsx_upload_response = client.post(
        f"/projects/{project_id}/files",
        data={"source_role": "config_workbook"},
        files={
            "file": (
                "order-config.xlsx",
                workbook_content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert xlsx_upload_response.status_code == 201

    xlsm_upload_response = client.post(
        f"/projects/{project_id}/files",
        data={"source_role": "config_workbook"},
        files={
            "file": (
                "order-config-macro.xlsm",
                workbook_content,
                "application/vnd.ms-excel.sheet.macroEnabled.12",
            )
        },
    )
    assert xlsm_upload_response.status_code == 201

    job_response = client.post(f"/projects/{project_id}/jobs/extract-spreadsheets")
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]

    with session_local() as session:
        job = session.scalar(select(Job).where(Job.id == job_id))
        assert job is not None
        process_extract_spreadsheets_job(
            session,
            job,
            sleep_seconds=0,
            storage_root=client.storage_root,
            max_rows_per_sheet=3,
        )

    extracted_response = client.get(f"/projects/{project_id}/extracted-content")

    assert extracted_response.status_code == 200
    extracted_contents = extracted_response.json()
    assert len(extracted_contents) == 2

    extracted_by_title = {
        extracted_content["title"]: extracted_content
        for extracted_content in extracted_contents
    }
    assert set(extracted_by_title) == {"order-config.xlsx", "order-config-macro.xlsm"}

    extracted_content = extracted_by_title["order-config.xlsx"]
    assert extracted_content["content_type"] == "spreadsheet"
    assert "Sheet: Configuration Values" in extracted_content["text_content"]
    assert "1: Parameter | Value | Formula" in extracted_content["text_content"]
    assert "2: Enable ATP | Yes | =LEN(B2)" in extracted_content["text_content"]
    assert "3: Lead Time | 5 | =B3*2" in extracted_content["text_content"]
    assert "Hidden Setup" not in extracted_content["text_content"]

    json_content = json.loads(extracted_content["json_content"])
    assert json_content["source_role"] == "config_workbook"
    assert json_content["workbook"] == {
        "sheet_count": 3,
        "sheet_names": ["Configuration Values", "Notes", "Hidden Setup"],
    }
    assert [sheet["name"] for sheet in json_content["sheets"]] == [
        "Configuration Values",
        "Notes",
    ]

    config_sheet = json_content["sheets"][0]
    assert config_sheet["max_row"] == 3
    assert config_sheet["max_column"] == 3
    assert config_sheet["non_empty_row_count"] == 3
    assert config_sheet["detected_header_rows"] == [1]
    assert config_sheet["is_likely_config_sheet"] is True
    assert config_sheet["rows"] == [
        {"row_number": 1, "values": ["Parameter", "Value", "Formula"]},
        {"row_number": 2, "values": ["Enable ATP", "Yes", "=LEN(B2)"]},
        {"row_number": 3, "values": ["Lead Time", 5, "=B3*2"]},
    ]


def test_extract_spreadsheet_handles_sparse_rows(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    from app.services.spreadsheet_extraction import extract_spreadsheet

    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Sparse Config"
    worksheet.append(["A", "B", "C", "D"])
    worksheet["D2"] = "Only populated cell in row"

    workbook_path = tmp_path / "sparse.xlsx"
    workbook.save(workbook_path)

    extracted = extract_spreadsheet(workbook_path, max_rows_per_sheet=10)
    sheet = extracted["json_content"]["sheets"][0]

    assert sheet["rows"][1] == {
        "row_number": 2,
        "values": [None, None, None, "Only populated cell in row"],
    }
    assert "2:  |  |  | Only populated cell in row" in extracted["text_content"]


def test_extract_all_processes_supported_file_types(
    client_and_session: tuple[TestClient, sessionmaker],
    tmp_path: Path,
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

    uploads = [
        (
            "kt-notes.txt",
            b"Welcome to the KT session.",
            "text/plain",
            "kt_transcript",
        ),
        (
            "order-management-fdd.docx",
            create_docx_fixture(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "fdd",
        ),
        (
            "order-flow.pptx",
            create_pptx_fixture(tmp_path),
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "kt_ppt",
        ),
        (
            "order-config.xlsx",
            create_workbook_fixture(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "config_workbook",
        ),
    ]

    for filename, content, content_type, source_role in uploads:
        upload_response = client.post(
            f"/projects/{project_id}/files",
            data={"source_role": source_role},
            files={"file": (filename, content, content_type)},
        )
        assert upload_response.status_code == 201

    job_response = client.post(f"/projects/{project_id}/jobs/extract-all")
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]

    with session_local() as session:
        job = session.scalar(select(Job).where(Job.id == job_id))
        assert job is not None
        process_extract_all_job(
            session,
            job,
            sleep_seconds=0,
            storage_root=client.storage_root,
            max_rows_per_sheet=3,
        )
        session.refresh(job)
        assert job.status == "completed"
        assert job.progress == 100
        assert job.message == (
            "Extracted 4 of 4 file(s) across all supported file types."
        )

    extracted_response = client.get(f"/projects/{project_id}/extracted-content")
    extracted_contents = extracted_response.json()
    assert sorted(content["content_type"] for content in extracted_contents) == [
        "docx",
        "pptx",
        "spreadsheet",
        "transcript",
    ]


def test_extract_all_completed_with_warnings_when_some_files_fail(
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

    valid_upload_response = client.post(
        f"/projects/{project_id}/files",
        data={"source_role": "kt_transcript"},
        files={"file": ("kt-notes.txt", b"Valid transcript", "text/plain")},
    )
    assert valid_upload_response.status_code == 201

    invalid_upload_response = client.post(
        f"/projects/{project_id}/files",
        data={"source_role": "supporting_doc"},
        files={
            "file": (
                "broken.docx",
                b"not a real docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert invalid_upload_response.status_code == 201

    job_response = client.post(f"/projects/{project_id}/jobs/extract-all")
    job_id = job_response.json()["id"]

    with session_local() as session:
        job = session.scalar(select(Job).where(Job.id == job_id))
        assert job is not None
        process_extract_all_job(
            session,
            job,
            sleep_seconds=0,
            storage_root=client.storage_root,
        )
        session.refresh(job)
        assert job.status == "completed_with_warnings"
        assert job.progress == 100
        assert "Extracted 1 of 2 file(s)" in (job.message or "")
        assert "broken.docx" in (job.message or "")

    extracted_response = client.get(f"/projects/{project_id}/extracted-content")
    extracted_contents = extracted_response.json()
    assert len(extracted_contents) == 1
    assert extracted_contents[0]["content_type"] == "transcript"


def test_extract_all_failed_when_all_files_fail(
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
        data={"source_role": "supporting_doc"},
        files={
            "file": (
                "broken.docx",
                b"not a real docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert upload_response.status_code == 201

    job_response = client.post(f"/projects/{project_id}/jobs/extract-all")
    job_id = job_response.json()["id"]

    with session_local() as session:
        job = session.scalar(select(Job).where(Job.id == job_id))
        assert job is not None
        process_extract_all_job(
            session,
            job,
            sleep_seconds=0,
            storage_root=client.storage_root,
        )
        session.refresh(job)
        assert job.status == "failed"
        assert job.progress == 100
        assert "Extracted 0 of 1 file(s)" in (job.message or "")

import json

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import EvidenceItem, ExtractedContent, Job, Project, UploadedFile
from app.services.evidence_index import build_evidence_index
from app.workers.local_worker import process_build_evidence_index_job


def create_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'evidence-index.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)
    return engine, session_local


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
    json_content: dict,
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


def test_fdd_evidence_gets_priority_100(tmp_path) -> None:
    engine, session_local = create_session(tmp_path)

    try:
        with session_local() as session:
            project = Project(customer_name="Vision Operations")
            session.add(project)
            session.commit()
            session.refresh(project)
            uploaded_file = add_uploaded_file(
                session,
                project.id,
                "fdd.docx",
                "fdd",
                "docx",
            )
            add_extracted_content(
                session,
                project.id,
                uploaded_file,
                "docx",
                "[Heading: Order Capture]\n\nOrders are validated in FDD.",
                {
                    "source_role": "fdd",
                    "headings": [{"text": "Order Capture", "level": 1}],
                    "tables": [{"index": 1, "rows": [["Field", "Value"]]}],
                },
            )

            evidence_items = build_evidence_index(session, project.id)

            assert evidence_items
            assert {item.priority for item in evidence_items} == {100}
            assert {item.evidence_type for item in evidence_items} >= {
                "heading",
                "paragraph",
                "table",
            }
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_workbook_evidence_gets_priority_60(tmp_path) -> None:
    engine, session_local = create_session(tmp_path)

    try:
        with session_local() as session:
            project = Project(customer_name="Vision Operations")
            session.add(project)
            session.commit()
            session.refresh(project)
            uploaded_file = add_uploaded_file(
                session,
                project.id,
                "config.xlsx",
                "config_workbook",
                "spreadsheet",
            )
            add_extracted_content(
                session,
                project.id,
                uploaded_file,
                "spreadsheet",
                "Sheet: Setup",
                {
                    "source_role": "config_workbook",
                    "sheets": [
                        {
                            "name": "Setup",
                            "max_column": 2,
                            "non_empty_row_count": 2,
                            "rows": [
                                {"row_number": 1, "values": ["Field", "Value"]},
                                {"row_number": 2, "values": ["ATP", "Enabled"]},
                            ],
                        }
                    ],
                },
            )

            evidence_items = build_evidence_index(session, project.id)

            assert {item.priority for item in evidence_items} == {60}
            assert {item.evidence_type for item in evidence_items} == {
                "workbook_sheet",
                "workbook_table",
            }
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_final_aud_sample_evidence_is_style_reference(tmp_path) -> None:
    engine, session_local = create_session(tmp_path)

    try:
        with session_local() as session:
            project = Project(customer_name="Vision Operations")
            session.add(project)
            session.commit()
            session.refresh(project)
            uploaded_file = add_uploaded_file(
                session,
                project.id,
                "sample-aud.docx",
                "final_aud_sample",
                "docx",
            )
            add_extracted_content(
                session,
                project.id,
                uploaded_file,
                "docx",
                "Sample AUD narrative style.",
                {"source_role": "final_aud_sample"},
            )

            evidence_items = build_evidence_index(session, project.id)

            assert evidence_items
            assert {item.priority for item in evidence_items} == {30}
            assert all(
                json.loads(item.json_data or "{}").get("style_reference") is True
                for item in evidence_items
            )
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_rerun_does_not_duplicate_evidence(tmp_path) -> None:
    engine, session_local = create_session(tmp_path)

    try:
        with session_local() as session:
            project = Project(customer_name="Vision Operations")
            session.add(project)
            session.commit()
            session.refresh(project)
            uploaded_file = add_uploaded_file(
                session,
                project.id,
                "fdd.docx",
                "fdd",
                "docx",
            )
            add_extracted_content(
                session,
                project.id,
                uploaded_file,
                "docx",
                "[Heading: Order Capture]\n\nOrders are validated in FDD.",
                {
                    "source_role": "fdd",
                    "headings": [{"text": "Order Capture", "level": 1}],
                },
            )

            first_run = build_evidence_index(session, project.id)
            second_run = build_evidence_index(session, project.id)
            count = session.scalar(
                select(func.count(EvidenceItem.id)).where(
                    EvidenceItem.project_id == project.id
                )
            )

            assert len(first_run) == len(second_run)
            assert count == len(first_run)
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_build_evidence_index_job_updates_status(tmp_path) -> None:
    engine, session_local = create_session(tmp_path)

    try:
        with session_local() as session:
            project = Project(customer_name="Vision Operations")
            session.add(project)
            session.commit()
            session.refresh(project)
            uploaded_file = add_uploaded_file(
                session,
                project.id,
                "fdd.docx",
                "fdd",
                "docx",
            )
            add_extracted_content(
                session,
                project.id,
                uploaded_file,
                "docx",
                "[Heading: Order Capture]\n\nOrders are validated in FDD.",
                {"source_role": "fdd", "headings": [{"text": "Order Capture"}]},
            )
            job = Job(project_id=project.id, job_type="build_evidence_index")
            session.add(job)
            session.commit()
            session.refresh(job)

            process_build_evidence_index_job(session, job, sleep_seconds=0)
            session.refresh(job)

            assert job.status == "completed"
            assert job.progress == 100
            assert "Evidence index contains" in (job.message or "")
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

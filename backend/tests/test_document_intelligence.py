import json
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.workers.local_worker as local_worker
from app.core.config import Settings
from app.db.base import Base
from app.models import ExtractedContent, Job, Project, UploadedFile
from app.services.document_intelligence import (
    DOCUMENT_UNDERSTANDING_CONTENT_TYPE,
    NoOpDocumentIntelligenceService,
    OCIDocumentUnderstandingService,
)
from app.workers.local_worker import process_enrich_document_understanding_job


class FakeDocumentClient:
    def __init__(self) -> None:
        self.created_details = None

    def create_processor_job(self, create_processor_job_details):
        self.created_details = create_processor_job_details
        return SimpleNamespace(data=SimpleNamespace(id="ocid1.processorjob.oc1..test"))

    def get_processor_job(self, processor_job_id: str):
        return SimpleNamespace(data=SimpleNamespace(lifecycle_state="SUCCEEDED"))


class FakeDocumentObjectStorageClient:
    def __init__(self) -> None:
        self.head_calls: list[tuple[str, str, str]] = []
        self.objects = {
            "projects/project-123/document_understanding/output/job-123/file-456/result.json": json.dumps(
                {
                    "documentMetadata": {"pageCount": 1},
                    "pages": [
                        {
                            "pageNumber": 1,
                            "lines": [{"text": "Invoice total is 42 USD."}],
                            "tables": [
                                {
                                    "cells": [
                                        [
                                            {"text": "Field"},
                                            {"text": "Value"},
                                        ],
                                        [
                                            {"text": "Total"},
                                            {"text": "42"},
                                        ],
                                    ]
                                }
                            ],
                        }
                    ],
                    "detectedDocumentTypes": [
                        {"documentType": "INVOICE", "confidence": 0.91}
                    ],
                }
            ).encode("utf-8")
        }

    def head_object(self, namespace: str, bucket_name: str, object_name: str) -> None:
        self.head_calls.append((namespace, bucket_name, object_name))

    def list_objects(self, namespace: str, bucket_name: str, prefix: str):
        return SimpleNamespace(
            data=SimpleNamespace(
                objects=[
                    SimpleNamespace(name=object_name)
                    for object_name in self.objects
                    if object_name.startswith(prefix)
                ]
            )
        )

    def get_object(self, namespace: str, bucket_name: str, object_name: str):
        return SimpleNamespace(
            data=SimpleNamespace(content=self.objects[object_name])
        )


class FakeDocumentIntelligenceService:
    provider_name = "oci_document_understanding"

    def __init__(self, fail_filenames: set[str] | None = None) -> None:
        self.fail_filenames = fail_filenames or set()
        self.calls: list[str] = []

    def analyze_document(
        self,
        project_id: str,
        uploaded_file: UploadedFile,
        job_id: str,
    ) -> dict:
        self.calls.append(uploaded_file.original_filename)
        if uploaded_file.original_filename in self.fail_filenames:
            raise RuntimeError("simulated DU failure")

        return {
            "processor_job_id": f"du-job-{uploaded_file.id}",
            "document_metadata": {"pageCount": 1},
            "pages": [{"page_number": 1, "text": "Validated text", "table_count": 0}],
            "detected_document_types": [],
            "tables": [],
            "raw_result_object_path": f"du/{uploaded_file.id}/result.json",
            "text": f"DU text for {uploaded_file.original_filename}",
        }


def create_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'document-intelligence.db').as_posix()}",
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


def add_project_file(
    session,
    filename: str,
    file_type: str,
    project_id: str,
) -> UploadedFile:
    uploaded_file = UploadedFile(
        project_id=project_id,
        original_filename=filename,
        file_type=file_type,
        storage_path=f"projects/{project_id}/uploads/{filename}",
        source_role="supporting_doc",
    )
    session.add(uploaded_file)
    session.flush()
    return uploaded_file


def test_noop_document_intelligence_provider_completes_without_output(
    tmp_path,
) -> None:
    engine, session_local = create_session(tmp_path)

    try:
        with session_local() as session:
            project = Project(customer_name="Vision Operations")
            session.add(project)
            session.commit()
            session.refresh(project)
            add_project_file(session, "support.pdf", "pdf", project.id)
            job = Job(
                project_id=project.id,
                job_type="enrich_with_document_understanding",
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            process_enrich_document_understanding_job(
                session,
                job,
                sleep_seconds=0,
                document_intelligence_service=NoOpDocumentIntelligenceService(),
            )
            session.refresh(job)

            assert job.status == "completed"
            assert job.message == (
                "No eligible files found for Document Understanding enrichment."
            )
            assert session.scalar(select(ExtractedContent)) is None
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_oci_document_understanding_service_normalizes_successful_result() -> None:
    document_client = FakeDocumentClient()
    object_storage_client = FakeDocumentObjectStorageClient()
    service = OCIDocumentUnderstandingService(
        settings=Settings(
            STORAGE_BACKEND="oci",
            OCI_NAMESPACE="tenantnamespace",
            OCI_BUCKET_NAME="aud-input",
            OCI_DOCUMENT_COMPARTMENT_OCID="ocid1.compartment.oc1..test",
            OCI_DOCUMENT_OUTPUT_BUCKET="aud-du-output",
            OCI_DOCUMENT_TIMEOUT_SECONDS=1,
            OCI_DOCUMENT_POLL_INTERVAL_SECONDS=0,
        ),
        document_client=document_client,
        object_storage_client=object_storage_client,
    )
    uploaded_file = UploadedFile(
        id="file-456",
        project_id="project-123",
        original_filename="support.pdf",
        file_type="pdf",
        storage_path="projects/project-123/uploads/file-456_support.pdf",
        source_role="supporting_doc",
    )

    result = service.analyze_document(
        project_id="project-123",
        uploaded_file=uploaded_file,
        job_id="job-123",
    )

    assert result is not None
    assert object_storage_client.head_calls == [
        ("tenantnamespace", "aud-input", uploaded_file.storage_path)
    ]
    assert document_client.created_details.compartment_id == (
        "ocid1.compartment.oc1..test"
    )
    assert document_client.created_details.output_location.bucket_name == (
        "aud-du-output"
    )
    assert result["processor_job_id"] == "ocid1.processorjob.oc1..test"
    assert result["text"] == "Page 1\nInvoice total is 42 USD."
    assert result["document_metadata"] == {"pageCount": 1}
    assert result["detected_document_types"] == [
        {"documentType": "INVOICE", "confidence": 0.91}
    ]
    assert result["tables"] == [
        {
            "index": 1,
            "page_number": 1,
            "rows": [["Field", "Value"], ["Total", "42"]],
        }
    ]


def test_document_understanding_partial_failure_completes_with_warnings(
    monkeypatch,
    tmp_path,
) -> None:
    engine, session_local = create_session(tmp_path)
    fake_service = FakeDocumentIntelligenceService(fail_filenames={"broken.pdf"})
    monkeypatch.setattr(
        local_worker,
        "get_settings",
        lambda: Settings(
            DOCUMENT_AI_PROVIDER="oci_document_understanding",
            OCI_DOCUMENT_ENABLE_PDF=True,
        ),
    )

    try:
        with session_local() as session:
            project = Project(customer_name="Vision Operations")
            session.add(project)
            session.commit()
            session.refresh(project)
            add_project_file(session, "valid.pdf", "pdf", project.id)
            broken_file = add_project_file(session, "broken.pdf", "pdf", project.id)
            session.add(
                ExtractedContent(
                    project_id=project.id,
                    uploaded_file_id=broken_file.id,
                    content_type="pdf_local_placeholder",
                    title="Existing local extraction",
                    text_content="Existing extraction stays usable.",
                    json_content="{}",
                )
            )
            job = Job(
                project_id=project.id,
                job_type="enrich_with_document_understanding",
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            process_enrich_document_understanding_job(
                session,
                job,
                sleep_seconds=0,
                document_intelligence_service=fake_service,
            )
            session.refresh(job)

            du_contents = list(
                session.scalars(
                    select(ExtractedContent).where(
                        ExtractedContent.content_type
                        == DOCUMENT_UNDERSTANDING_CONTENT_TYPE
                    )
                )
            )
            assert job.status == "completed_with_warnings"
            assert "broken.pdf" in (job.message or "")
            assert len(du_contents) == 1
            assert du_contents[0].title == (
                "valid.pdf - OCI Document Understanding"
            )
            assert fake_service.calls == ["valid.pdf", "broken.pdf"]
            assert (
                session.scalar(
                    select(ExtractedContent).where(
                        ExtractedContent.uploaded_file_id == broken_file.id,
                        ExtractedContent.content_type == "pdf_local_placeholder",
                    )
                )
                is not None
            )
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_document_understanding_failure_warns_when_existing_extraction_is_available(
    monkeypatch,
    tmp_path,
) -> None:
    engine, session_local = create_session(tmp_path)
    fake_service = FakeDocumentIntelligenceService(fail_filenames={"broken.pdf"})
    monkeypatch.setattr(
        local_worker,
        "get_settings",
        lambda: Settings(
            DOCUMENT_AI_PROVIDER="oci_document_understanding",
            OCI_DOCUMENT_ENABLE_PDF=True,
        ),
    )

    try:
        with session_local() as session:
            project = Project(customer_name="Vision Operations")
            session.add(project)
            session.commit()
            session.refresh(project)
            broken_file = add_project_file(session, "broken.pdf", "pdf", project.id)
            session.add(
                ExtractedContent(
                    project_id=project.id,
                    uploaded_file_id=broken_file.id,
                    content_type="pdf_local_placeholder",
                    title="Existing local extraction",
                    text_content="Existing extraction stays usable.",
                    json_content="{}",
                )
            )
            job = Job(
                project_id=project.id,
                job_type="enrich_with_document_understanding",
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            process_enrich_document_understanding_job(
                session,
                job,
                sleep_seconds=0,
                document_intelligence_service=fake_service,
            )
            session.refresh(job)

            assert job.status == "completed_with_warnings"
            assert "existing extraction remains usable" in (job.message or "")
            assert "broken.pdf" in (job.message or "")
            assert (
                session.scalar(
                    select(ExtractedContent).where(
                        ExtractedContent.content_type
                        == DOCUMENT_UNDERSTANDING_CONTENT_TYPE
                    )
                )
                is None
            )
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_document_understanding_skips_xlsx_when_disabled(
    monkeypatch,
    tmp_path,
) -> None:
    engine, session_local = create_session(tmp_path)
    fake_service = FakeDocumentIntelligenceService()
    monkeypatch.setattr(
        local_worker,
        "get_settings",
        lambda: Settings(
            DOCUMENT_AI_PROVIDER="oci_document_understanding",
            OCI_DOCUMENT_ENABLE_XLSX=False,
        ),
    )

    try:
        with session_local() as session:
            project = Project(customer_name="Vision Operations")
            session.add(project)
            session.commit()
            session.refresh(project)
            add_project_file(session, "config.xlsx", "spreadsheet", project.id)
            job = Job(
                project_id=project.id,
                job_type="enrich_with_document_understanding",
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            process_enrich_document_understanding_job(
                session,
                job,
                sleep_seconds=0,
                document_intelligence_service=fake_service,
            )
            session.refresh(job)

            assert job.status == "completed"
            assert job.message == (
                "No eligible files found for Document Understanding enrichment."
            )
            assert fake_service.calls == []
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

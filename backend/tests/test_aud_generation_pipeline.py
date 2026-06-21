import json
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.workers.local_worker as local_worker
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import (
    AUDGenerationRun,
    ExtractedContent,
    GeneratedDocument,
    Job,
    Project,
    UploadedFile,
)
from app.api.routes_aud_generation import resume_failed_generation_run
from app.services.aud_pipeline_orchestrator import (
    AUDPipelineOrchestrator,
    AUDPipelineStage,
    get_or_create_generation_run,
    parse_json_list,
)
from app.services.job_queue import LocalJobQueueService, get_job_queue_service


ALL_STAGE_JOB_TYPES = [
    "classify_files",
    "extract_all",
    "enrich_with_document_understanding",
    "transcribe_media",
    "generate_aud_plan",
    "build_evidence_index",
    "generate_source_summaries_ai",
    "enhance_aud_plan_ai",
    "build_section_evidence_packs",
    "extract_open_points",
    "refine_open_points_ai",
    "generate_section_drafts_ai",
    "generate_docx",
]


class FakeDocumentIntelligenceService:
    provider_name = "oci_document_understanding"

    def analyze_document(
        self,
        project_id: str,
        uploaded_file: UploadedFile,
        job_id: str,
    ) -> dict:
        raise RuntimeError("simulated DU failure")


@pytest.fixture()
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'aud-generation-api.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
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
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def create_session(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'aud-generation.db').as_posix()}",
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


def add_project(session: Session) -> Project:
    project = Project(customer_name="Vision Operations", module_name="Order Management")
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def add_uploaded_file(
    session: Session,
    project_id: str,
    filename: str,
    source_role: str = "supporting_doc",
) -> UploadedFile:
    uploaded_file = UploadedFile(
        project_id=project_id,
        original_filename=filename,
        storage_path=f"projects/{project_id}/uploads/{filename}",
        source_role=source_role,
    )
    session.add(uploaded_file)
    session.commit()
    session.refresh(uploaded_file)
    return uploaded_file


def build_success_processors(calls: list[str]):
    def make_processor(job_type: str):
        def processor(session: Session, job: Job) -> None:
            calls.append(job.job_type)
            if job_type == "generate_docx":
                session.add(
                    GeneratedDocument(
                        project_id=job.project_id,
                        filename="aud.docx",
                        storage_path=f"projects/{job.project_id}/outputs/aud.docx",
                    )
                )
            job.status = "completed"
            job.progress = 100
            job.message = f"{job_type} complete"
            session.commit()

        return processor

    return {job_type: make_processor(job_type) for job_type in ALL_STAGE_JOB_TYPES}


def run_orchestrator(
    session: Session,
    project: Project,
    processors,
) -> AUDGenerationRun:
    generation_run = get_or_create_generation_run(session, project.id)
    orchestrator = AUDPipelineOrchestrator(
        session=session,
        generation_run=generation_run,
        stage_processors=processors,
    )
    return orchestrator.run()


def test_post_generate_aud_creates_orchestration_job(client: TestClient) -> None:
    project_response = client.post("/projects", json={"customer_name": "Vision"})
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/generate-aud")

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["message"] == "AUD generation started"
    assert payload["job_id"]

    status_response = client.get(f"/projects/{project_id}/generate-aud/status")
    assert status_response.status_code == 200
    assert status_response.json()["job_id"] == payload["job_id"]
    assert status_response.json()["status"] == "queued"


def test_failed_generation_run_can_be_requeued_for_resume(tmp_path: Path) -> None:
    engine, session_local = create_session(tmp_path)

    try:
        with session_local() as session:
            project = add_project(session)
            job = Job(
                project_id=project.id,
                job_type="generate_aud",
                status="failed",
                progress=1,
                message="LLM response was not valid JSON.",
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            generation_run = get_or_create_generation_run(
                session,
                project_id=project.id,
                run_id=job.id,
            )
            generation_run.status = "failed"
            generation_run.current_stage = AUDPipelineStage.ENHANCE_AUD_PLAN_AI.value
            generation_run.failed_stage = AUDPipelineStage.ENHANCE_AUD_PLAN_AI.value
            generation_run.error_message = "LLM response was not valid JSON."
            generation_run.completed_stages_json = json.dumps(
                [
                    AUDPipelineStage.VALIDATE_PROJECT_INPUTS.value,
                    AUDPipelineStage.EXTRACT_CONTENT.value,
                ]
            )
            session.commit()

            resumed_job = resume_failed_generation_run(
                job.id,
                session,
                LocalJobQueueService(),
            )

            session.refresh(generation_run)
            assert resumed_job is not None
            assert resumed_job.id == job.id
            assert resumed_job.status == "pending"
            assert generation_run.status == "queued"
            assert generation_run.failed_stage is None
            assert generation_run.error_message is None
            assert parse_json_list(generation_run.completed_stages_json) == [
                AUDPipelineStage.VALIDATE_PROJECT_INPUTS.value,
                AUDPipelineStage.EXTRACT_CONTENT.value,
            ]
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_orchestrator_runs_stages_in_expected_order(tmp_path: Path) -> None:
    engine, session_local = create_session(tmp_path)
    calls: list[str] = []

    try:
        with session_local() as session:
            project = add_project(session)
            add_uploaded_file(session, project.id, "fdd.docx", source_role="fdd")

            run = run_orchestrator(
                session,
                project,
                build_success_processors(calls),
            )

            assert run.status == "completed"
            assert parse_json_list(run.completed_stages_json) == [
                stage.value for stage in AUDPipelineStage
            ]
            assert calls == [
                "classify_files",
                "extract_all",
                "generate_aud_plan",
                "build_evidence_index",
                "generate_source_summaries_ai",
                "enhance_aud_plan_ai",
                "build_section_evidence_packs",
                "extract_open_points",
                "refine_open_points_ai",
                "generate_section_drafts_ai",
                "generate_docx",
            ]
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_pdf_file_triggers_document_understanding_stage(tmp_path: Path) -> None:
    engine, session_local = create_session(tmp_path)
    calls: list[str] = []

    try:
        with session_local() as session:
            project = add_project(session)
            add_uploaded_file(session, project.id, "support.pdf")

            run = run_orchestrator(
                session,
                project,
                build_success_processors(calls),
            )

            assert run.status == "completed"
            assert "enrich_with_document_understanding" in calls
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_media_file_triggers_oci_speech_stage(tmp_path: Path) -> None:
    engine, session_local = create_session(tmp_path)
    calls: list[str] = []

    try:
        with session_local() as session:
            project = add_project(session)
            add_uploaded_file(session, project.id, "kt-session.mp4", "kt_session")

            run = run_orchestrator(
                session,
                project,
                build_success_processors(calls),
            )

            assert run.status == "completed"
            assert "transcribe_media" in calls
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_critical_stage_failure_marks_run_failed_with_failed_stage(
    tmp_path: Path,
) -> None:
    engine, session_local = create_session(tmp_path)
    calls: list[str] = []
    processors = build_success_processors(calls)

    def fail_evidence_index(session: Session, job: Job) -> None:
        calls.append(job.job_type)
        job.status = "failed"
        job.message = "simulated evidence failure"
        session.commit()

    processors["build_evidence_index"] = fail_evidence_index

    try:
        with session_local() as session:
            project = add_project(session)
            add_uploaded_file(session, project.id, "fdd.docx", source_role="fdd")

            run = run_orchestrator(session, project, processors)

            assert run.status == "failed"
            assert run.failed_stage == AUDPipelineStage.BUILD_EVIDENCE_INDEX.value
            assert "simulated evidence failure" in (run.error_message or "")
            assert parse_json_list(run.completed_stages_json) == [
                AUDPipelineStage.VALIDATE_PROJECT_INPUTS.value,
                AUDPipelineStage.EXTRACT_CONTENT.value,
                AUDPipelineStage.ENRICH_DOCUMENT_UNDERSTANDING.value,
                AUDPipelineStage.TRANSCRIBE_MEDIA.value,
                AUDPipelineStage.GENERATE_INITIAL_AUD_PLAN.value,
            ]
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_ai_plan_enhancement_failure_marks_run_failed(
    tmp_path: Path,
) -> None:
    engine, session_local = create_session(tmp_path)
    calls: list[str] = []
    processors = build_success_processors(calls)

    def fail_ai_plan_enhancement(session: Session, job: Job) -> None:
        calls.append(job.job_type)
        raise RuntimeError("LLM response was not valid JSON.")

    processors["enhance_aud_plan_ai"] = fail_ai_plan_enhancement

    try:
        with session_local() as session:
            project = add_project(session)
            add_uploaded_file(session, project.id, "fdd.docx", source_role="fdd")

            run = run_orchestrator(session, project, processors)

            warnings = parse_json_list(run.warnings_json)
            assert run.status == "failed"
            assert run.failed_stage == AUDPipelineStage.ENHANCE_AUD_PLAN_AI.value
            assert "not valid JSON" in (run.error_message or "")
            assert warnings == []
            assert "build_section_evidence_packs" not in calls
            assert "generate_docx" not in calls
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_open_points_refinement_failure_warns_and_continues_when_fallback_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine, session_local = create_session(tmp_path)
    calls: list[str] = []
    processors = build_success_processors(calls)

    def fail_open_points_refinement(session: Session, job: Job) -> None:
        calls.append(job.job_type)
        raise RuntimeError("LLM refinement failed.")

    processors["refine_open_points_ai"] = fail_open_points_refinement
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: Settings(ALLOW_RAW_OPEN_POINTS_FALLBACK=True, _env_file=None),
    )

    try:
        with session_local() as session:
            project = add_project(session)
            add_uploaded_file(session, project.id, "fdd.docx", source_role="fdd")

            run = run_orchestrator(session, project, processors)

            assert run.status == "completed_with_warnings"
            warnings = parse_json_list(run.warnings_json)
            assert warnings == [
                "LLM Open Points enhancement failed; continuing without raw Open Points fallback"
            ]
            assert "generate_docx" in calls
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_file_level_du_failure_becomes_warning_when_extraction_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine, session_local = create_session(tmp_path)
    calls: list[str] = []
    processors = build_success_processors(calls)
    monkeypatch.setattr(
        local_worker,
        "get_settings",
        lambda: Settings(
            DOCUMENT_AI_PROVIDER="oci_document_understanding",
            OCI_DOCUMENT_ENABLE_PDF=True,
        ),
    )

    def run_du(session: Session, job: Job) -> None:
        calls.append(job.job_type)
        local_worker.process_enrich_document_understanding_job(
            session,
            job,
            sleep_seconds=0,
            document_intelligence_service=FakeDocumentIntelligenceService(),
        )

    processors["enrich_with_document_understanding"] = run_du

    try:
        with session_local() as session:
            project = add_project(session)
            uploaded_file = add_uploaded_file(session, project.id, "broken.pdf")
            session.add(
                ExtractedContent(
                    project_id=project.id,
                    uploaded_file_id=uploaded_file.id,
                    content_type="pdf_local_placeholder",
                    title="Existing extraction",
                    text_content="Existing extraction remains usable.",
                    json_content=json.dumps({}),
                )
            )
            session.commit()

            run = run_orchestrator(session, project, processors)

            assert run.status == "completed_with_warnings"
            warnings = parse_json_list(run.warnings_json)
            assert len(warnings) == 1
            assert "existing extraction remains usable" in warnings[0]
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_final_docx_document_id_is_stored_on_completion(tmp_path: Path) -> None:
    engine, session_local = create_session(tmp_path)
    calls: list[str] = []

    try:
        with session_local() as session:
            project = add_project(session)
            add_uploaded_file(session, project.id, "fdd.docx", source_role="fdd")

            run = run_orchestrator(
                session,
                project,
                build_success_processors(calls),
            )

            document = session.scalar(
                select(GeneratedDocument).where(
                    GeneratedDocument.project_id == project.id
                )
            )
            assert document is not None
            assert run.status == "completed"
            assert run.final_document_id == document.id
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

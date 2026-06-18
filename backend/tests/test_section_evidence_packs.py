import json
from collections.abc import Generator
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import AUDPlan, EvidenceItem, Job, Project, SectionEvidencePack, UploadedFile
from app.services.job_queue import LocalJobQueueService, get_job_queue_service
from app.services.section_evidence_pack import build_section_evidence_packs
from app.workers.local_worker import process_build_section_evidence_packs_job


def make_session(tmp_path: Path) -> tuple[sessionmaker, object]:
    database_path = tmp_path / "section-packs.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)
    return session_local, engine


def create_project_with_plan_and_evidence(session) -> Project:
    project = Project(customer_name="Vision Operations")
    session.add(project)
    session.commit()
    session.refresh(project)

    fdd_file = UploadedFile(
        project_id=project.id,
        original_filename="fdd.docx",
        file_type="docx",
        storage_path=f"projects/{project.id}/uploads/fdd.docx",
        source_role="fdd",
    )
    config_file = UploadedFile(
        project_id=project.id,
        original_filename="config.xlsx",
        file_type="spreadsheet",
        storage_path=f"projects/{project.id}/uploads/config.xlsx",
        source_role="config_workbook",
    )
    transcript_file = UploadedFile(
        project_id=project.id,
        original_filename="kt.txt",
        file_type="transcript_text",
        storage_path=f"projects/{project.id}/uploads/kt.txt",
        source_role="kt_transcript",
    )
    session.add_all([fdd_file, config_file, transcript_file])
    session.commit()
    session.refresh(fdd_file)
    session.refresh(config_file)
    session.refresh(transcript_file)

    session.add(
        AUDPlan(
            project_id=project.id,
            status="draft",
            plan_json=json.dumps(
                {
                    "sections": [
                        {
                            "section_id": "section-001-enterprise-structure",
                            "title": "Enterprise Structure",
                            "source_roles": ["fdd", "config_workbook", "kt_transcript"],
                            "evidence_item_ids": ["fdd-evidence", "config-evidence", "transcript-evidence"],
                        }
                    ]
                }
            ),
        )
    )
    session.add_all(
        [
            EvidenceItem(
                id="fdd-evidence",
                project_id=project.id,
                source_uploaded_file_id=fdd_file.id,
                evidence_type="paragraph",
                source_role="fdd",
                title="Enterprise Structure",
                text="FDD describes the enterprise structure hierarchy.",
                priority=100,
                confidence="high",
            ),
            EvidenceItem(
                id="config-evidence",
                project_id=project.id,
                source_uploaded_file_id=config_file.id,
                evidence_type="workbook_table",
                source_role="config_workbook",
                title="Enterprise Structure Configuration",
                text="Business unit and inventory organization setup rows.",
                priority=60,
                confidence="medium",
            ),
            EvidenceItem(
                id="transcript-evidence",
                project_id=project.id,
                source_uploaded_file_id=transcript_file.id,
                evidence_type="transcript_segment",
                source_role="kt_transcript",
                title="Enterprise Structure discussion",
                text="Presenter emphasized the hierarchy and deferred legal entity details.",
                priority=80,
                confidence="medium",
            ),
        ]
    )
    session.commit()
    return project


def test_fdd_config_and_transcript_evidence_are_bucketed(tmp_path: Path) -> None:
    session_local, engine = make_session(tmp_path)

    try:
        with session_local() as session:
            project = create_project_with_plan_and_evidence(session)
            packs = build_section_evidence_packs(
                session,
                project.id,
                settings=Settings(_env_file=None),
            )
            pack_payload = json.loads(packs[0].pack_json)

        assert pack_payload["golden_source_present"] is True
        assert pack_payload["primary_evidence"][0]["evidence_item_id"] == "fdd-evidence"
        assert (
            pack_payload["configuration_evidence"][0]["evidence_item_id"]
            == "config-evidence"
        )
        assert (
            pack_payload["transcript_context"][0]["evidence_item_id"]
            == "transcript-evidence"
        )
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_pack_size_is_bounded(tmp_path: Path) -> None:
    session_local, engine = make_session(tmp_path)

    try:
        with session_local() as session:
            project = create_project_with_plan_and_evidence(session)
            session.add(
                EvidenceItem(
                    id="huge-fdd-evidence",
                    project_id=project.id,
                    evidence_type="paragraph",
                    source_role="fdd",
                    title="Enterprise Structure",
                    text="Enterprise Structure detail. " * 1000,
                    priority=100,
                    confidence="high",
                )
            )
            session.commit()

            packs = build_section_evidence_packs(
                session,
                project.id,
                settings=Settings(SECTION_EVIDENCE_MAX_CHARS=3500, _env_file=None),
            )

        assert len(packs[0].pack_json) <= 3500
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_config_evidence_can_be_primary_when_no_narrative_source_matches(
    tmp_path: Path,
) -> None:
    session_local, engine = make_session(tmp_path)

    try:
        with session_local() as session:
            project = Project(customer_name="Vision Operations")
            session.add(project)
            session.commit()
            session.refresh(project)

            config_file = UploadedFile(
                project_id=project.id,
                original_filename="config.xlsx",
                file_type="spreadsheet",
                storage_path=f"projects/{project.id}/uploads/config.xlsx",
                source_role="config_workbook",
            )
            session.add(config_file)
            session.commit()
            session.refresh(config_file)
            session.add(
                AUDPlan(
                    project_id=project.id,
                    status="draft",
                    plan_json=json.dumps(
                        {
                            "sections": [
                                {
                                    "section_id": "section-001-config",
                                    "title": "Pricing Setup",
                                }
                            ]
                        }
                    ),
                )
            )
            session.add(
                EvidenceItem(
                    id="config-only-evidence",
                    project_id=project.id,
                    source_uploaded_file_id=config_file.id,
                    evidence_type="workbook_table",
                    source_role="config_workbook",
                    title="Pricing Setup",
                    text="Pricing setup configuration rows.",
                    priority=60,
                    confidence="medium",
                )
            )
            session.commit()

            packs = build_section_evidence_packs(
                session,
                project.id,
                settings=Settings(_env_file=None),
            )
            pack_payload = json.loads(packs[0].pack_json)

        assert (
            pack_payload["primary_evidence"][0]["evidence_item_id"]
            == "config-only-evidence"
        )
        assert pack_payload["configuration_evidence"] == []
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_build_section_evidence_packs_job_and_list_route(tmp_path: Path) -> None:
    session_local, engine = make_session(tmp_path)
    app = create_app(create_tables_on_startup=False)

    def override_get_db() -> Generator:
        with session_local() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_job_queue_service] = lambda: LocalJobQueueService()

    try:
        with session_local() as session:
            project = create_project_with_plan_and_evidence(session)
            job = Job(project_id=project.id, job_type="build_section_evidence_packs")
            session.add(job)
            session.commit()
            job_id = job.id
            project_id = project.id

            process_build_section_evidence_packs_job(session, job, sleep_seconds=0)
            session.refresh(job)
            assert job.status == "completed"

        with TestClient(app) as client:
            create_response = client.post(
                f"/projects/{project_id}/jobs/build-section-evidence-packs"
            )
            list_response = client.get(
                f"/projects/{project_id}/section-evidence-packs"
            )

        assert create_response.status_code == 201
        assert create_response.json()["job_type"] == "build_section_evidence_packs"
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        with session_local() as session:
            assert session.get(Job, job_id) is not None
            assert session.scalar(select(SectionEvidencePack)) is not None
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

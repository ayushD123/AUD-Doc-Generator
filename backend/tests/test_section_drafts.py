import json
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import AUDSectionDraft, Job, OpenPoint, Project, SectionEvidencePack
from app.services.job_queue import LocalJobQueueService, get_job_queue_service
from app.services.llm import LLMInvalidJSONError
import app.services.section_drafting_ai as section_drafting_ai
from app.services.section_drafting_ai import (
    SectionDraftGenerationResult,
    build_section_draft_prompt,
    generate_section_drafts_ai,
)
from app.workers.local_worker import process_generate_section_drafts_ai_job


class FakeDraftLLMService:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.prompts: list[str] = []
        self.system_prompts: list[str | None] = []

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> str:
        return "{}"

    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        schema_name: str | None = None,
    ) -> dict:
        self.prompts.append(prompt)
        self.system_prompts.append(system_prompt)

        if self.fail:
            raise LLMInvalidJSONError("LLM response was not valid JSON.")

        return {
            "section_id": "section-001-enterprise-structure",
            "title": "Enterprise Structure",
            "draft_text": (
                "The enterprise structure is defined based on validated FDD "
                "evidence and supporting configuration context."
            ),
            "confidence": "high",
            "used_evidence_item_ids": ["fdd-evidence"],
            "included_tables": [{"evidence_item_id": "config-evidence"}],
            "included_images": [],
            "unsupported_details": ["Legal entity ownership was not confirmed."],
            "open_point_candidates": [
                {
                    "topic": "Enterprise Structure",
                    "question": "Confirm legal entity ownership for the hierarchy.",
                    "evidence": "Drafting AI flagged missing ownership details.",
                }
            ],
            "placeholders": [],
        }


class RetryDraftLLMService(FakeDraftLLMService):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        schema_name: str | None = None,
    ) -> dict:
        self.calls += 1
        if self.calls == 1:
            self.prompts.append(prompt)
            self.system_prompts.append(system_prompt)
            raise LLMInvalidJSONError("LLM response was not valid JSON.")

        return super().generate_json(
            prompt,
            system_prompt=system_prompt,
            schema_name=schema_name,
        )


def make_session(tmp_path: Path) -> tuple[sessionmaker, object]:
    database_path = tmp_path / "section-drafts.db"
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


def create_project_with_pack(session, supported: bool = True) -> Project:
    project = Project(customer_name="Vision Operations")
    session.add(project)
    session.commit()
    session.refresh(project)

    pack_payload = {
        "section_id": "section-001-enterprise-structure",
        "section_title": "Enterprise Structure",
        "source_priority_rules": ["fdd: FDD wins over lower-priority sources."],
        "golden_source_present": True,
        "primary_evidence": [
            {
                "evidence_item_id": "fdd-evidence",
                "source_role": "fdd",
                "evidence_type": "paragraph",
                "title": "Enterprise Structure",
                "text": "FDD describes the enterprise structure.",
                "priority": 100,
            }
        ]
        if supported
        else [],
        "supporting_evidence": [],
        "configuration_evidence": [],
        "transcript_context": [],
        "image_candidates": [],
        "table_candidates": [],
        "open_point_candidates": [],
        "excluded_evidence": [],
        "missing_information": [],
    }
    session.add(
        SectionEvidencePack(
            project_id=project.id,
            section_id="section-001-enterprise-structure",
            section_title="Enterprise Structure",
            pack_json=json.dumps(pack_payload),
        )
    )
    session.commit()
    return project


def test_mocked_llm_draft_saved_open_point_inserted_and_details_preserved(
    tmp_path: Path,
) -> None:
    session_local, engine = make_session(tmp_path)
    fake_llm = FakeDraftLLMService()

    try:
        with session_local() as session:
            project = create_project_with_pack(session)
            result = generate_section_drafts_ai(
                session,
                project.id,
                llm_service=fake_llm,
                settings=Settings(_env_file=None),
            )
            draft_payload = json.loads(result.drafts[0].draft_json or "{}")
            open_points = list(
                session.scalars(
                    select(OpenPoint).where(OpenPoint.project_id == project.id)
                )
            )

        assert len(result.drafts) == 1
        assert result.warnings == []
        assert result.drafts[0].confidence == "high"
        assert draft_payload["used_evidence_item_ids"] == ["fdd-evidence"]
        assert draft_payload["unsupported_details"] == [
            "Legal entity ownership was not confirmed."
        ]
        assert len(open_points) == 1
        assert "Confirm legal entity ownership" in open_points[0].question
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_invalid_json_is_handled_as_warning(tmp_path: Path) -> None:
    session_local, engine = make_session(tmp_path)
    fake_llm = FakeDraftLLMService(fail=True)

    try:
        with session_local() as session:
            project = create_project_with_pack(session)
            result = generate_section_drafts_ai(
                session,
                project.id,
                llm_service=fake_llm,
                settings=Settings(_env_file=None),
            )

        assert result.drafts == []
        assert len(result.warnings) == 1
        assert "not valid JSON" in result.warnings[0]
        assert len(fake_llm.prompts) == 2
        assert fake_llm.system_prompts[0] is None
        assert fake_llm.system_prompts[1] is not None
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_invalid_json_is_retried_once_with_strict_section_draft_prompt(
    tmp_path: Path,
) -> None:
    session_local, engine = make_session(tmp_path)
    fake_llm = RetryDraftLLMService()

    try:
        with session_local() as session:
            project = create_project_with_pack(session)
            result = generate_section_drafts_ai(
                session,
                project.id,
                llm_service=fake_llm,
                settings=Settings(_env_file=None),
            )

        assert len(result.drafts) == 1
        assert result.warnings == []
        assert fake_llm.calls == 2
        assert fake_llm.system_prompts[0] is None
        assert fake_llm.system_prompts[1] is not None
        assert "previous section draft response was not valid" in (
            fake_llm.system_prompts[1] or ""
        )
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_generated_only_sections_are_still_sent_to_ai_drafting(
    tmp_path: Path,
) -> None:
    session_local, engine = make_session(tmp_path)
    fake_llm = FakeDraftLLMService()

    try:
        with session_local() as session:
            project = Project(customer_name="Vision Operations")
            session.add(project)
            session.commit()
            session.refresh(project)
            session.add(
                SectionEvidencePack(
                    project_id=project.id,
                    section_id="section-003-table-of-contents",
                    section_title="Table of Contents",
                    pack_json=json.dumps(
                        {
                            "section_id": "section-003-table-of-contents",
                            "section_title": "Table of Contents",
                            "primary_evidence": [{"text": "irrelevant"}],
                            "supporting_evidence": [],
                            "configuration_evidence": [],
                            "transcript_context": [],
                            "image_candidates": [],
                            "table_candidates": [],
                        }
                    ),
                )
            )
            session.commit()

            result = generate_section_drafts_ai(
                session,
                project.id,
                llm_service=fake_llm,
                settings=Settings(_env_file=None),
            )

        assert len(result.drafts) == 1
        assert result.warnings == []
        assert len(fake_llm.prompts) == 1
        assert "Table of Contents" in fake_llm.prompts[0]
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_section_draft_prompt_bounds_without_corrupting_pack_json() -> None:
    settings = Settings(OCI_GENAI_MAX_INPUT_CHARS=9000, _env_file=None)
    pack_payload = {
        "section_id": "section-001-enterprise-structure",
        "section_title": "Enterprise Structure",
        "primary_evidence": [
            {
                "evidence_item_id": f"evidence-{index}",
                "source_role": "fdd",
                "text": "Detailed section evidence. " * 200,
                "priority": 100,
            }
            for index in range(80)
        ],
        "supporting_evidence": [],
        "configuration_evidence": [],
        "transcript_context": [],
        "image_candidates": [],
        "table_candidates": [],
    }

    prompt = build_section_draft_prompt(pack_payload, settings=settings)
    pack_json = prompt.split("Evidence pack:\n", 1)[1].rsplit(
        "\nEnd evidence pack.",
        1,
    )[0]

    assert len(prompt) <= 9000
    assert prompt.endswith("End evidence pack.")
    json.loads(pack_json)


def test_no_supported_evidence_forces_placeholder_and_low_confidence(
    tmp_path: Path,
) -> None:
    session_local, engine = make_session(tmp_path)
    fake_llm = FakeDraftLLMService()

    try:
        with session_local() as session:
            project = create_project_with_pack(session, supported=False)
            result = generate_section_drafts_ai(
                session,
                project.id,
                llm_service=fake_llm,
                settings=Settings(_env_file=None),
            )
            draft_payload = json.loads(result.drafts[0].draft_json or "{}")

        assert result.drafts[0].confidence == "low"
        assert result.drafts[0].draft_text == (
            "<Content not available in provided source material>"
        )
        assert draft_payload["placeholders"] == [
            "<Content not available in provided source material>"
        ]
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_generate_section_drafts_job_and_list_route(tmp_path: Path) -> None:
    session_local, engine = make_session(tmp_path)
    app = create_app(create_tables_on_startup=False)

    def override_get_db() -> Generator:
        with session_local() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_job_queue_service] = lambda: LocalJobQueueService()

    try:
        with session_local() as session:
            project = create_project_with_pack(session)
            project_id = project.id
            draft = AUDSectionDraft(
                project_id=project.id,
                section_id="section-001-enterprise-structure",
                title="Enterprise Structure",
                draft_text="Existing draft.",
                draft_json="{}",
                confidence="medium",
            )
            session.add(draft)
            session.commit()

        with TestClient(app) as client:
            create_response = client.post(
                f"/projects/{project_id}/jobs/generate-section-drafts-ai"
            )
            list_response = client.get(f"/projects/{project_id}/section-drafts")

        assert create_response.status_code == 201
        assert create_response.json()["job_type"] == "generate_section_drafts_ai"
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_generate_section_drafts_job_message_includes_warning_details(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session_local, engine = make_session(tmp_path)

    try:
        with session_local() as session:
            project = create_project_with_pack(session)
            draft = AUDSectionDraft(
                project_id=project.id,
                section_id="section-001-enterprise-structure",
                title="Enterprise Structure",
                draft_text="Draft.",
                draft_json="{}",
                confidence="medium",
            )
            job = Job(project_id=project.id, job_type="generate_section_drafts_ai")
            session.add_all([draft, job])
            session.commit()

            def fake_generate_section_drafts_ai(session, project_id):
                return SectionDraftGenerationResult(
                    drafts=[draft],
                    warnings=[
                        (
                            "section-002-pricing/Pricing: "
                            "LLMInvalidJSONError: LLM response was not valid JSON."
                        )
                    ],
                )

            monkeypatch.setattr(
                section_drafting_ai,
                "generate_section_drafts_ai",
                fake_generate_section_drafts_ai,
            )

            process_generate_section_drafts_ai_job(session, job, sleep_seconds=0)

            assert job.status == "completed_with_warnings"
            assert "Generated 1 section draft(s) with 1 warning(s)." in (
                job.message or ""
            )
            assert "section-002-pricing/Pricing" in (job.message or "")
            assert "LLM response was not valid JSON" in (job.message or "")
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

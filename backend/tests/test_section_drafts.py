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
from app.models import AUDSectionDraft, OpenPoint, Project, SectionEvidencePack
from app.services.job_queue import LocalJobQueueService, get_job_queue_service
from app.services.llm import LLMInvalidJSONError
from app.services.section_drafting_ai import (
    build_section_draft_prompt,
    generate_section_drafts_ai,
)


class FakeDraftLLMService:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.prompts: list[str] = []

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

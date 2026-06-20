import json
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import EvidenceItem, Project, SourceSummary, UploadedFile
from app.services.llm import LLMInvalidJSONError
from app.services.llm.base import get_prompt_body_budget
from app.services.source_summary_service import (
    EvidenceSourceGroup,
    build_source_summary_prompt,
    generate_source_summaries_ai,
)


class FakeLLMService:
    def __init__(self, fail_on_prompt: str | None = None) -> None:
        self.fail_on_prompt = fail_on_prompt
        self.prompts: list[str] = []

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
    ) -> str:
        return '{"status":"ok"}'

    def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        schema_name: str | None = None,
    ) -> dict:
        self.prompts.append(prompt)

        if self.fail_on_prompt and self.fail_on_prompt in prompt:
            raise LLMInvalidJSONError("LLM response was not valid JSON.")

        return {
            "source_role": "fdd",
            "summary": "Order management requirements are described.",
            "important_topics": ["Order Management"],
            "tables_or_configurations": [],
            "processes": ["Order capture"],
            "screenshots_or_images_to_consider": [],
            "open_or_unresolved_items": [],
            "source_confidence": "high",
            "aud_usage_guidance": "Use as source-backed summary.",
        }


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

    with TestClient(app) as test_client:
        yield test_client, testing_session_local

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def create_project_with_evidence(
    session: Session,
    *,
    source_role: str = "fdd",
    evidence_text: str = "Order capture requirements are handled in Oracle.",
) -> tuple[Project, UploadedFile]:
    project = Project(customer_name="Vision Operations")
    session.add(project)
    session.commit()
    session.refresh(project)

    uploaded_file = UploadedFile(
        project_id=project.id,
        original_filename=f"{source_role}.docx",
        file_type="docx",
        storage_path=f"projects/{project.id}/uploads/{source_role}.docx",
        source_role=source_role,
    )
    session.add(uploaded_file)
    session.commit()
    session.refresh(uploaded_file)

    session.add(
        EvidenceItem(
            project_id=project.id,
            source_uploaded_file_id=uploaded_file.id,
            evidence_type="paragraph",
            source_role=source_role,
            title="Order Capture",
            text=evidence_text,
            priority=100 if source_role == "fdd" else 70,
            confidence="high",
            json_data="{}",
        )
    )
    session.commit()
    return project, uploaded_file


def test_generate_source_summaries_ai_with_mocked_llm(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    _, session_local = client_and_session
    fake_llm = FakeLLMService()

    with session_local() as session:
        project, uploaded_file = create_project_with_evidence(session)
        result = generate_source_summaries_ai(
            session,
            project.id,
            llm_service=fake_llm,
            settings=Settings(_env_file=None),
        )

        summaries = list(
            session.scalars(
                select(SourceSummary).where(SourceSummary.project_id == project.id)
            )
        )

    assert len(result.summaries) == 1
    assert result.warnings == []
    assert len(summaries) == 1
    assert summaries[0].source_uploaded_file_id == uploaded_file.id
    assert summaries[0].source_role == "fdd"
    assert summaries[0].summary_type == "fdd_summary"
    assert summaries[0].summary_text == "Order management requirements are described."
    assert "Order Management" in (summaries[0].summary_json or "")


def test_invalid_json_warning_behavior_continues_other_sources(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    _, session_local = client_and_session
    fake_llm = FakeLLMService(fail_on_prompt='"source_role":"fdd"')

    with session_local() as session:
        project, _ = create_project_with_evidence(session, source_role="fdd")
        uploaded_file = UploadedFile(
            project_id=project.id,
            original_filename="kt_ppt.pptx",
            file_type="pptx",
            storage_path=f"projects/{project.id}/uploads/kt_ppt.pptx",
            source_role="kt_ppt",
        )
        session.add(uploaded_file)
        session.commit()
        session.refresh(uploaded_file)
        session.add(
            EvidenceItem(
                project_id=project.id,
                source_uploaded_file_id=uploaded_file.id,
                evidence_type="slide",
                source_role="kt_ppt",
                title="Billing",
                text="Slide explains billing process screenshots.",
                priority=70,
                confidence="medium",
                json_data="{}",
            )
        )
        session.commit()

        result = generate_source_summaries_ai(
            session,
            project.id,
            llm_service=fake_llm,
            settings=Settings(_env_file=None),
        )

    assert len(result.summaries) == 1
    assert len(result.warnings) == 1
    assert "not valid JSON" in result.warnings[0]


def test_fdd_prompt_includes_golden_source_instruction() -> None:
    group = EvidenceSourceGroup(
        source_uploaded_file_id="file-1",
        source_role="fdd",
        evidence_items=[
            EvidenceItem(
                project_id="project-1",
                evidence_type="heading",
                source_role="fdd",
                title="Enterprise Structure",
                text="Enterprise Structure",
                priority=100,
                confidence="high",
            )
        ],
    )

    prompt = build_source_summary_prompt(group, settings=Settings(_env_file=None))

    assert "FDD is the golden source" in prompt
    assert "highest authority" in prompt


def test_final_aud_prompt_includes_style_only_instruction() -> None:
    group = EvidenceSourceGroup(
        source_uploaded_file_id="file-2",
        source_role="final_aud_sample",
        evidence_items=[
            EvidenceItem(
                project_id="project-1",
                evidence_type="paragraph",
                source_role="final_aud_sample",
                title="Sample AUD",
                text="Sample document uses short paragraphs.",
                priority=30,
                confidence="medium",
            )
        ],
    )

    prompt = build_source_summary_prompt(group, settings=Settings(_env_file=None))

    assert "Summarize style and structure only" in prompt
    assert "Do not treat sample business content as authoritative" in prompt


def test_source_summary_prompt_reserves_space_for_llm_wrapper_text() -> None:
    settings = Settings(OCI_GENAI_MAX_INPUT_CHARS=12000, _env_file=None)
    group = EvidenceSourceGroup(
        source_uploaded_file_id="file-1",
        source_role="fdd",
        evidence_items=[
            EvidenceItem(
                project_id="project-1",
                evidence_type="paragraph",
                source_role="fdd",
                title=f"Topic {index}",
                text="Detailed source evidence. " * 100,
                priority=100,
                confidence="high",
            )
            for index in range(40)
        ],
    )

    prompt = build_source_summary_prompt(group, settings=settings)

    assert len(prompt) <= get_prompt_body_budget(settings.OCI_GENAI_MAX_INPUT_CHARS)
    assert prompt.endswith("Do not include markdown or commentary.")
    json.loads(prompt.split("Inputs:\n", 1)[1].split("\n\nFinal reminder:", 1)[0])


def test_source_summary_prompt_bounds_without_cutting_prompt_tail() -> None:
    settings = Settings(OCI_GENAI_MAX_INPUT_CHARS=9000, _env_file=None)
    group = EvidenceSourceGroup(
        source_uploaded_file_id="file-1",
        source_role="kt_transcript",
        evidence_items=[
            EvidenceItem(
                project_id="project-1",
                evidence_type="transcript",
                source_role="kt_transcript",
                title=f"Topic {index}",
                text="Detailed transcript evidence. " * 200,
                priority=80,
                confidence="medium",
            )
            for index in range(80)
        ],
    )

    prompt = build_source_summary_prompt(group, settings=settings)

    assert len(prompt) <= get_prompt_body_budget(settings.OCI_GENAI_MAX_INPUT_CHARS)
    assert "Return strict JSON only" in prompt
    assert prompt.endswith("Do not include markdown or commentary.")
    inputs = json.loads(
        prompt.split("Inputs:\n", 1)[1].split("\n\nFinal reminder:", 1)[0]
    )
    assert isinstance(inputs["evidence_items"], list)


def test_list_source_summaries(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, session_local = client_and_session

    with session_local() as session:
        project = Project(customer_name="Vision Operations")
        session.add(project)
        session.commit()
        session.refresh(project)
        project_id = project.id
        session.add(
            SourceSummary(
                project_id=project.id,
                source_role="fdd",
                summary_type="fdd_summary",
                summary_text="FDD summary.",
                summary_json="{}",
            )
        )
        session.commit()

    response = client.get(f"/projects/{project_id}/source-summaries")

    assert response.status_code == 200
    summaries = response.json()
    assert len(summaries) == 1
    assert summaries[0]["source_role"] == "fdd"
    assert summaries[0]["summary_type"] == "fdd_summary"


def test_list_source_summaries_returns_404_for_unknown_project(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, _ = client_and_session

    response = client.get("/projects/missing-project/source-summaries")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."

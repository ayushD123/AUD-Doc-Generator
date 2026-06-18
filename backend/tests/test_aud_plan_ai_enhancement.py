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
from app.models import AUDPlan, EvidenceItem, Project, SourceSummary, UploadedFile
from app.services.aud_plan_ai_enhancement import (
    build_enhance_aud_plan_prompt,
    enhance_aud_plan_ai,
)
from app.services.llm import LLMInvalidJSONError
from app.services.llm.base import get_prompt_body_budget


class FakeAUDPlanLLMService:
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
            "document_strategy": {
                "template_source": "default_scm_template",
                "content_golden_source": "fdd",
                "default_template_required": True,
                "notes": ["FDD remains authoritative."],
            },
            "sections": [
                {
                    "section_id": "section-001-order-capture",
                    "title": "Order Capture",
                    "include_in_aud": True,
                    "reason": "Supported by FDD evidence.",
                    "source_roles": ["fdd"],
                    "source_summary_ids": ["summary-1"],
                    "evidence_item_ids": ["evidence-1"],
                    "content_priority": "fdd",
                    "expected_content_type": "narrative",
                    "confidence": "high",
                    "missing_info_handling": "placeholder",
                },
                {
                    "section_id": "section-999-documents-referred",
                    "title": "Documents Referred",
                    "include_in_aud": True,
                    "reason": "Model suggested it, but app should remove it.",
                    "source_roles": [],
                    "source_summary_ids": [],
                    "evidence_item_ids": [],
                    "content_priority": "mixed",
                    "expected_content_type": "narrative",
                    "confidence": "low",
                    "missing_info_handling": "omit",
                },
            ],
            "image_strategy": [],
            "table_strategy": [],
            "open_point_candidates": [],
            "warnings": [],
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


def create_project_with_plan(session: Session) -> Project:
    project = Project(customer_name="Vision Operations", module_name="Order Management")
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
    session.add_all([fdd_file, config_file])
    session.commit()
    session.refresh(fdd_file)
    session.refresh(config_file)

    session.add(
        AUDPlan(
            project_id=project.id,
            status="draft",
            plan_json=json.dumps(
                {
                    "project_id": project.id,
                    "status": "draft",
                    "generation_basis": "fdd_headings",
                    "default_template_required": True,
                    "sections": [
                        {
                            "section_id": "section-001-cover-page",
                            "title": "Cover Page",
                            "source_role_basis": "aud_template",
                        },
                        {
                            "section_id": "section-002-order-capture",
                            "title": "Order Capture",
                            "source_role_basis": "fdd",
                        },
                    ],
                }
            ),
        )
    )
    session.add(
        SourceSummary(
            id="summary-1",
            project_id=project.id,
            source_uploaded_file_id=fdd_file.id,
            source_role="fdd",
            summary_type="fdd_summary",
            summary_text="FDD confirms order capture requirements.",
            summary_json=json.dumps(
                {
                    "source_confidence": "high",
                    "important_topics": ["Order Capture"],
                    "aud_usage_guidance": "Use as golden source.",
                }
            ),
        )
    )
    session.add(
        SourceSummary(
            id="summary-2",
            project_id=project.id,
            source_uploaded_file_id=config_file.id,
            source_role="config_workbook",
            summary_type="config_summary",
            summary_text="Workbook contains configuration validation facts.",
            summary_json=json.dumps(
                {
                    "source_confidence": "medium",
                    "important_topics": ["Configuration"],
                    "aud_usage_guidance": "Validate only.",
                }
            ),
        )
    )
    session.add(
        EvidenceItem(
            id="evidence-1",
            project_id=project.id,
            source_uploaded_file_id=fdd_file.id,
            evidence_type="paragraph",
            source_role="fdd",
            title="Order Capture",
            text="Order capture is supported by the FDD.",
            priority=100,
            confidence="high",
        )
    )
    session.commit()
    return project


def test_enhancement_prompt_contains_fdd_golden_source_rule() -> None:
    prompt = build_enhance_aud_plan_prompt(
        deterministic_plan={"sections": []},
        source_priority_report={
            "golden_source_files": [{"source_role": "fdd"}],
            "source_roles_present": ["fdd"],
            "recommended_default_template_needed": True,
        },
        source_summaries=[],
        evidence_items=[],
        settings=Settings(_env_file=None),
    )

    assert "FDD is the golden source if present" in prompt
    assert "FDD wins" in prompt


def test_enhancement_prompt_keeps_config_workbook_non_primary_when_fdd_exists() -> None:
    prompt = build_enhance_aud_plan_prompt(
        deterministic_plan={"sections": []},
        source_priority_report={
            "golden_source_files": [{"source_role": "fdd"}],
            "source_roles_present": ["fdd", "config_workbook"],
            "recommended_default_template_needed": True,
        },
        source_summaries=[],
        evidence_items=[],
        settings=Settings(_env_file=None),
    )

    assert "Configuration workbook validates and enriches" in prompt
    assert "do not treat it as primary narrative when FDD exists" in prompt


def test_enhancement_prompt_reserves_space_for_llm_wrapper_text() -> None:
    settings = Settings(OCI_GENAI_MAX_INPUT_CHARS=12000, _env_file=None)
    evidence_items = [
        EvidenceItem(
            project_id="project-1",
            evidence_type="paragraph",
            source_role="fdd",
            title=f"Topic {index}",
            text="Detailed FDD evidence. " * 100,
            priority=100,
            confidence="high",
        )
        for index in range(60)
    ]

    prompt = build_enhance_aud_plan_prompt(
        deterministic_plan={"sections": [{"title": "Enterprise Structure"}]},
        source_priority_report={"source_roles_present": ["fdd"]},
        source_summaries=[],
        evidence_items=evidence_items,
        settings=settings,
    )

    assert len(prompt) <= get_prompt_body_budget(settings.OCI_GENAI_MAX_INPUT_CHARS)


def test_enhancement_prompt_requests_compact_output_and_compacts_plan_sections() -> None:
    prompt = build_enhance_aud_plan_prompt(
        deterministic_plan={
            "sections": [
                {
                    "section_id": "section-001",
                    "title": "Order Capture",
                    "source_role_basis": "fdd",
                    "large_unused_field": "x" * 2000,
                }
            ]
        },
        source_priority_report={"source_roles_present": ["fdd"]},
        source_summaries=[],
        evidence_items=[],
        settings=Settings(_env_file=None),
    )

    assert "Return no more than 25 sections" in prompt
    assert "Do not write draft section content" in prompt
    assert "large_unused_field" not in prompt


def test_enhanced_plan_saved_without_overwriting_deterministic_sections(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    _, session_local = client_and_session
    fake_llm = FakeAUDPlanLLMService()

    with session_local() as session:
        project = create_project_with_plan(session)
        aud_plan = enhance_aud_plan_ai(
            session,
            project.id,
            llm_service=fake_llm,
            settings=Settings(_env_file=None),
        )
        plan_payload = json.loads(aud_plan.plan_json)

    assert "ai_enhanced_plan" in plan_payload
    assert [section["title"] for section in plan_payload["sections"]] == [
        "Cover Page",
        "Order Capture",
    ]
    enhanced_titles = [
        section["title"] for section in plan_payload["ai_enhanced_plan"]["sections"]
    ]
    assert enhanced_titles == ["Order Capture"]
    assert plan_payload["ai_enhanced_plan"]["document_strategy"][
        "content_golden_source"
    ] == "fdd"


def test_invalid_json_handled_without_corrupting_existing_plan(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    _, session_local = client_and_session
    fake_llm = FakeAUDPlanLLMService(fail=True)

    with session_local() as session:
        project = create_project_with_plan(session)
        existing_plan = session.scalar(
            select(AUDPlan).where(AUDPlan.project_id == project.id)
        )
        assert existing_plan is not None
        original_plan_json = existing_plan.plan_json

        with pytest.raises(LLMInvalidJSONError, match="not valid JSON"):
            enhance_aud_plan_ai(
                session,
                project.id,
                llm_service=fake_llm,
                settings=Settings(_env_file=None),
            )

        session.refresh(existing_plan)
        assert existing_plan.plan_json == original_plan_json

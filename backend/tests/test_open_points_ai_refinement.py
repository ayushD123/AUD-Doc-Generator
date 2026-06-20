import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.models import (
    AUDSectionDraft,
    EvidenceItem,
    OpenPoint,
    Project,
    SourceSummary,
)
from app.services.open_points_ai_refinement import (
    OpenPointCandidateContext,
    build_refine_open_points_prompt,
    refine_open_points_ai,
)


class FakeOpenPointsLLMService:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
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
        return self.payload


def make_session(tmp_path: Path) -> tuple[sessionmaker, object]:
    database_path = tmp_path / "open-points-ai.db"
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


def create_project(session) -> Project:
    project = Project(customer_name="Vision Operations", module_name="Order Management")
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def test_closed_items_are_excluded_from_refined_open_points(tmp_path: Path) -> None:
    session_local, engine = make_session(tmp_path)
    fake_llm = FakeOpenPointsLLMService(
        {
            "open_points": [
                {
                    "topic": "Pricing",
                    "question": "Pricing approval setup is complete.",
                    "status": "Closed",
                    "source_open_point_ids": [],
                    "evidence_item_ids": [],
                    "reason": "Resolved by business.",
                }
            ],
            "excluded_items": [],
        }
    )

    try:
        with session_local() as session:
            project = create_project(session)
            result = refine_open_points_ai(
                session,
                project.id,
                llm_service=fake_llm,
                settings=Settings(_env_file=None),
            )
            open_points = list(
                session.scalars(
                    select(OpenPoint).where(OpenPoint.project_id == project.id)
                )
            )

        assert result.open_points == []
        assert result.excluded_items == [
            {"text": "Pricing approval setup is complete.", "reason": "resolved"}
        ]
        assert open_points == []
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_refinement_prompt_reserves_space_without_corrupting_inputs_json() -> None:
    settings = Settings(OCI_GENAI_MAX_INPUT_CHARS=12000, _env_file=None)
    existing_open_points = [
        OpenPoint(
            project_id="project-1",
            topic=f"Topic {index}",
            question="Need confirmation. " * 80,
            status="Open",
            evidence="Detailed evidence. " * 80,
        )
        for index in range(80)
    ]
    candidates = [
        OpenPointCandidateContext(
            candidate_id=f"candidate-{index}",
            source="source_summary",
            topic="Topic",
            text="Candidate text. " * 80,
        )
        for index in range(160)
    ]

    prompt = build_refine_open_points_prompt(
        existing_open_points=existing_open_points,
        candidates=candidates,
        fdd_context=[
            {"id": "fdd-1", "summary_text": "FDD context. " * 120},
        ],
        settings=settings,
    )

    assert len(prompt) <= 12000
    json.loads(prompt.split("Inputs:\n", 1)[1])


def test_fdd_answered_lower_priority_conflict_is_excluded(tmp_path: Path) -> None:
    session_local, engine = make_session(tmp_path)

    try:
        with session_local() as session:
            project = create_project(session)
            ppt_evidence = EvidenceItem(
                project_id=project.id,
                evidence_type="slide_text",
                source_role="kt_ppt",
                title="Approval Conflict",
                text="PPT says approval setup conflicts with the FDD.",
                priority=70,
            )
            session.add_all(
                [
                    SourceSummary(
                        project_id=project.id,
                        source_role="fdd",
                        summary_type="fdd_summary",
                        summary_text="FDD clearly states approvals are not required.",
                        summary_json=json.dumps(
                            {
                                "source_confidence": "high",
                                "open_or_unresolved_items": [],
                            }
                        ),
                    ),
                    ppt_evidence,
                ]
            )
            session.commit()
            session.refresh(ppt_evidence)

            fake_llm = FakeOpenPointsLLMService(
                {
                    "open_points": [
                        {
                            "topic": "Approvals",
                            "question": "Resolve conflict between PPT and FDD.",
                            "status": "Open",
                            "source_open_point_ids": [],
                            "evidence_item_ids": [ppt_evidence.id],
                            "reason": "Lower-priority conflict needs review.",
                        }
                    ],
                    "excluded_items": [],
                }
            )
            result = refine_open_points_ai(
                session,
                project.id,
                llm_service=fake_llm,
                settings=Settings(_env_file=None),
            )

        assert result.open_points == []
        assert result.excluded_items == [
            {
                "text": "Resolve conflict between PPT and FDD.",
                "reason": "answered_by_fdd",
            }
        ]
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_fdd_needs_more_discussion_is_included(tmp_path: Path) -> None:
    session_local, engine = make_session(tmp_path)
    fake_llm = FakeOpenPointsLLMService(
        {
            "open_points": [
                {
                    "topic": "Pricing",
                    "question": "Confirm pricing approval flow with business.",
                    "status": "Open",
                    "source_open_point_ids": [],
                    "evidence_item_ids": [],
                    "reason": "FDD says needs more discussion.",
                }
            ],
            "excluded_items": [],
        }
    )

    try:
        with session_local() as session:
            project = create_project(session)
            session.add(
                SourceSummary(
                    project_id=project.id,
                    source_role="fdd",
                    summary_type="fdd_summary",
                    summary_text="Pricing approval flow needs more discussion.",
                    summary_json=json.dumps(
                        {
                            "source_confidence": "medium",
                            "open_or_unresolved_items": [
                                "Pricing approval flow needs more discussion."
                            ],
                        }
                    ),
                )
            )
            session.commit()

            result = refine_open_points_ai(
                session,
                project.id,
                llm_service=fake_llm,
                settings=Settings(_env_file=None),
            )
            open_points = list(
                session.scalars(
                    select(OpenPoint).where(OpenPoint.project_id == project.id)
                )
            )

        assert len(result.open_points) == 1
        assert len(open_points) == 1
        assert open_points[0].status == "Open"
        assert open_points[0].question == "Confirm pricing approval flow with business."
        evidence_payload = json.loads(open_points[0].evidence or "{}")
        assert evidence_payload["refinement_job_type"] == "refine_open_points_ai"
        assert evidence_payload["evidence_text"] == "FDD says needs more discussion."
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_duplicate_refinement_marks_source_removed_and_creates_one_refined_item(
    tmp_path: Path,
) -> None:
    session_local, engine = make_session(tmp_path)

    try:
        with session_local() as session:
            project = create_project(session)
            existing = OpenPoint(
                project_id=project.id,
                topic="Old Topic",
                question="Need to confirm shipping cutover.",
                status="Open",
                evidence="Original deterministic extraction.",
            )
            session.add(
                AUDSectionDraft(
                    project_id=project.id,
                    section_id="section-001-shipping",
                    title="Shipping",
                    draft_text="Draft.",
                    draft_json=json.dumps(
                        {
                            "open_point_candidates": [
                                "Need to confirm shipping cutover."
                            ],
                            "used_evidence_item_ids": [],
                        }
                    ),
                )
            )
            session.add(existing)
            session.commit()
            session.refresh(existing)

            fake_llm = FakeOpenPointsLLMService(
                {
                    "open_points": [
                        {
                            "topic": "Shipping",
                            "question": "Confirm shipping cutover timing.",
                            "status": "Open",
                            "source_open_point_ids": [existing.id],
                            "evidence_item_ids": [],
                            "reason": "Cleaned duplicate wording.",
                        },
                        {
                            "topic": "Shipping",
                            "question": "Confirm shipping cutover timing.",
                            "status": "Open",
                            "source_open_point_ids": [existing.id],
                            "evidence_item_ids": [],
                            "reason": "Duplicate duplicate.",
                        },
                    ],
                    "excluded_items": [],
                }
            )
            result = refine_open_points_ai(
                session,
                project.id,
                llm_service=fake_llm,
                settings=Settings(_env_file=None),
            )
            session.refresh(existing)
            all_open_points = list(
                session.scalars(
                    select(OpenPoint)
                    .where(OpenPoint.project_id == project.id)
                    .order_by(OpenPoint.created_at.asc())
                )
            )

        assert len(result.open_points) == 1
        assert result.excluded_items == [
            {"text": "Confirm shipping cutover timing.", "reason": "duplicate"}
        ]
        assert existing.status == "Removed"
        assert [point.status for point in all_open_points] == ["Removed", "Open"]
        assert all_open_points[1].question == "Confirm shipping cutover timing."
        refined_evidence = json.loads(all_open_points[1].evidence or "{}")
        assert refined_evidence["evidence_text"] == "Original deterministic extraction."
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.scripts.oracle_smoke_test import run_smoke_test


def test_oracle_smoke_test_exercises_workflow_with_mocked_provider() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    result = run_smoke_test(
        session_factory=session_factory,
        provider="oracle",
        dialect=engine.dialect.name,
    )

    assert result.failed == []
    assert "created project" in result.passed
    assert "created uploaded file metadata" in result.passed
    assert "created job" in result.passed
    assert "inserted representative CLOB and JSON content" in result.passed
    assert "inserted generated document metadata and run status" in result.passed
    assert "read generated document list" in result.passed
    assert "cleaned up smoke test records" in result.passed

    inspector = inspect(engine)
    assert "projects" in inspector.get_table_names()
    with session_factory() as session:
        assert session.execute(text("SELECT COUNT(*) FROM projects")).scalar_one() == 0


def test_oracle_smoke_test_requires_oracle_provider() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    result = run_smoke_test(
        session_factory=session_factory,
        provider="sqlite",
        dialect=engine.dialect.name,
    )

    assert result.ok is False
    assert result.failed == [
        "DB provider must be oracle for this smoke test; got sqlite."
    ]

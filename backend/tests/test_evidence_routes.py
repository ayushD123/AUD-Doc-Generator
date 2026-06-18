from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import EvidenceItem, Project


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


def test_list_evidence_items(
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
            EvidenceItem(
                project_id=project.id,
                evidence_type="heading",
                source_role="fdd",
                title="Order Capture",
                text="Order Capture",
                priority=100,
                confidence="high",
                json_data="{}",
            )
        )
        session.commit()

    response = client.get(f"/projects/{project_id}/evidence-items")

    assert response.status_code == 200
    evidence_items = response.json()
    assert len(evidence_items) == 1
    assert evidence_items[0]["evidence_type"] == "heading"
    assert evidence_items[0]["priority"] == 100


def test_list_evidence_items_returns_404_for_unknown_project(
    client_and_session: tuple[TestClient, sessionmaker],
) -> None:
    client, _ = client_and_session

    response = client.get("/projects/missing-project/evidence-items")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."

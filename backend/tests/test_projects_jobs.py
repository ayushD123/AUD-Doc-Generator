from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import Job, Project, UploadedFile
from app.services.job_queue import LocalJobQueueService, get_job_queue_service


class FakeJobQueueService:
    def __init__(self) -> None:
        self.published_jobs: list[dict[str, str]] = []

    def publish_job(self, job: Job) -> None:
        self.published_jobs.append(
            {
                "job_id": job.id,
                "project_id": job.project_id,
                "job_type": job.job_type,
            }
        )


@pytest.fixture()
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
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
    app.dependency_overrides[get_job_queue_service] = LocalJobQueueService

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_create_and_get_project(client: TestClient) -> None:
    create_response = client.post(
        "/projects",
        json={
            "name": "Asha Mehta",
            "email_id": "asha.mehta@example.com",
            "customer_name": "Vision Operations",
            "module_name": "Order Management",
        },
    )

    assert create_response.status_code == 201
    created_project = create_response.json()
    assert created_project["name"] == "Asha Mehta"
    assert created_project["email_id"] == "asha.mehta@example.com"
    assert created_project["customer_name"] == "Vision Operations"
    assert created_project["module_name"] == "Order Management"
    assert created_project["status"] == "draft"
    assert created_project["id"]
    assert created_project["created_at"]
    assert created_project["updated_at"]

    get_response = client.get(f"/projects/{created_project['id']}")

    assert get_response.status_code == 200
    assert get_response.json()["id"] == created_project["id"]


def test_list_projects(client: TestClient) -> None:
    client.post("/projects", json={"customer_name": "Customer A"})
    client.post("/projects", json={"customer_name": "Customer B"})

    response = client.get("/projects")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_project_returns_404_for_unknown_project(client: TestClient) -> None:
    response = client.get("/projects/missing-project")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_delete_project_removes_project(client: TestClient) -> None:
    create_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Order Management",
        },
    )
    project_id = create_response.json()["id"]

    delete_response = client.delete(f"/projects/{project_id}")

    assert delete_response.status_code == 204
    get_response = client.get(f"/projects/{project_id}")
    assert get_response.status_code == 404


def test_delete_project_returns_404_for_unknown_project(client: TestClient) -> None:
    response = client.delete("/projects/missing-project")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_and_list_project_jobs(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    create_response = client.post(
        f"/projects/{project_id}/jobs",
        json={
            "job_type": "aud_generation",
            "message": "Queued for local processing.",
        },
    )

    assert create_response.status_code == 201
    created_job = create_response.json()
    assert created_job["project_id"] == project_id
    assert created_job["job_type"] == "aud_generation"
    assert created_job["status"] == "pending"
    assert created_job["progress"] == 0
    assert created_job["message"] == "Queued for local processing."

    list_response = client.get(f"/projects/{project_id}/jobs")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == created_job["id"]


def test_create_classify_files_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/classify-files")

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "classify_files"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "File classification job queued."


def test_create_job_publishes_to_configured_queue_service(
    client: TestClient,
) -> None:
    fake_queue_service = FakeJobQueueService()
    client.app.dependency_overrides[get_job_queue_service] = lambda: fake_queue_service
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/generate-docx")

    assert response.status_code == 201
    job = response.json()
    assert fake_queue_service.published_jobs == [
        {
            "job_id": job["id"],
            "project_id": project_id,
            "job_type": "generate_docx",
        }
    ]


def test_create_classify_files_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post("/projects/missing-project/jobs/classify-files")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_extract_transcripts_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/extract-transcripts")

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "extract_transcripts"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "Transcript extraction job queued."


def test_create_extract_transcripts_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post("/projects/missing-project/jobs/extract-transcripts")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_extract_docx_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/extract-docx")

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "extract_docx"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "DOCX extraction job queued."


def test_create_extract_docx_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post("/projects/missing-project/jobs/extract-docx")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_transcribe_media_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/transcribe-media")

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "transcribe_media"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "Media transcription job queued."


def test_create_transcribe_media_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post("/projects/missing-project/jobs/transcribe-media")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_extract_pptx_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/extract-pptx")

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "extract_pptx"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "PPTX extraction job queued."


def test_create_extract_pptx_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post("/projects/missing-project/jobs/extract-pptx")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_extract_spreadsheets_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/extract-spreadsheets")

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "extract_spreadsheets"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "Spreadsheet extraction job queued."


def test_create_extract_spreadsheets_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post("/projects/missing-project/jobs/extract-spreadsheets")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_extract_all_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/extract-all")

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "extract_all"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "Extract all files job queued."


def test_create_extract_all_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post("/projects/missing-project/jobs/extract-all")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_generate_aud_plan_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/generate-aud-plan")

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "generate_aud_plan"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "AUD plan generation job queued."


def test_create_generate_aud_plan_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post("/projects/missing-project/jobs/generate-aud-plan")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_enrich_document_understanding_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(
        f"/projects/{project_id}/jobs/enrich-document-understanding"
    )

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "enrich_with_document_understanding"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "Document Understanding enrichment job queued."


def test_create_enrich_document_understanding_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post(
        "/projects/missing-project/jobs/enrich-document-understanding"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_build_evidence_index_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/build-evidence-index")

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "build_evidence_index"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "Evidence index build job queued."


def test_create_build_evidence_index_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post("/projects/missing-project/jobs/build-evidence-index")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_generate_source_summaries_ai_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(
        f"/projects/{project_id}/jobs/generate-source-summaries-ai"
    )

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "generate_source_summaries_ai"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "AI source summary generation job queued."


def test_create_generate_source_summaries_ai_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post(
        "/projects/missing-project/jobs/generate-source-summaries-ai"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_enhance_aud_plan_ai_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/enhance-aud-plan-ai")

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "enhance_aud_plan_ai"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "AI AUD plan enhancement job queued."


def test_create_enhance_aud_plan_ai_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post("/projects/missing-project/jobs/enhance-aud-plan-ai")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_build_section_evidence_packs_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(
        f"/projects/{project_id}/jobs/build-section-evidence-packs"
    )

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "build_section_evidence_packs"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "Section evidence pack build job queued."


def test_create_build_section_evidence_packs_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post(
        "/projects/missing-project/jobs/build-section-evidence-packs"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_generate_section_drafts_ai_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(
        f"/projects/{project_id}/jobs/generate-section-drafts-ai"
    )

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "generate_section_drafts_ai"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "AI section draft generation job queued."


def test_create_generate_section_drafts_ai_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post(
        "/projects/missing-project/jobs/generate-section-drafts-ai"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_extract_open_points_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/extract-open-points")

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "extract_open_points"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "Open points extraction job queued."


def test_create_refine_open_points_ai_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/refine-open-points-ai")

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "refine_open_points_ai"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "AI Open Points refinement job queued."


def test_create_extract_open_points_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post("/projects/missing-project/jobs/extract-open-points")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_refine_open_points_ai_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post("/projects/missing-project/jobs/refine-open-points-ai")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_generate_docx_job(client: TestClient) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(f"/projects/{project_id}/jobs/generate-docx")

    assert response.status_code == 201
    job = response.json()
    assert job["project_id"] == project_id
    assert job["job_type"] == "generate_docx"
    assert job["status"] == "pending"
    assert job["progress"] == 0
    assert job["message"] == "DOCX generation job queued."


def test_create_generate_docx_job_accepts_generation_options(
    client: TestClient,
) -> None:
    project_response = client.post(
        "/projects",
        json={
            "customer_name": "Vision Operations",
            "module_name": "Receivables",
        },
    )
    project_id = project_response.json()["id"]

    response = client.post(
        f"/projects/{project_id}/jobs/generate-docx",
        json={
            "use_ai_drafts": True,
            "include_draft_sections": False,
            "include_images": False,
            "include_open_points": True,
        },
    )

    assert response.status_code == 201
    job = response.json()
    assert job["job_type"] == "generate_docx"
    assert '"include_draft_sections": false' in job["message"]
    assert '"include_images": false' in job["message"]


def test_create_generate_docx_job_returns_404_for_unknown_project(
    client: TestClient,
) -> None:
    response = client.post("/projects/missing-project/jobs/generate-docx")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_list_jobs_returns_404_for_unknown_project(client: TestClient) -> None:
    response = client.get("/projects/missing-project/jobs")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."


def test_create_job_returns_404_for_unknown_project(client: TestClient) -> None:
    response = client.post(
        "/projects/missing-project/jobs",
        json={"job_type": "aud_generation"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found."

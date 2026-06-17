import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.workers.oci_queue_worker as oci_queue_worker
from app.core.config import Settings
from app.db.base import Base
from app.models import Job
from app.models import Project
from app.services.job_queue import OCIJobQueueService


class FakeOCIQueueClient:
    def __init__(self) -> None:
        self.put_calls: list[tuple[str, object]] = []

    def put_messages(self, queue_id: str, details: object) -> None:
        self.put_calls.append((queue_id, details))


def test_oci_job_queue_publishes_job_payload_with_mock_client() -> None:
    client = FakeOCIQueueClient()
    queue = OCIJobQueueService(
        settings=Settings(
            JOB_QUEUE_BACKEND="oci",
            OCI_QUEUE_OCID="ocid1.queue.oc1..example",
            OCI_QUEUE_ENDPOINT="https://queue.us-ashburn-1.oci.oraclecloud.com",
        ),
        client=client,
        message_details_factory=lambda content: {"messages": [{"content": content}]},
    )
    job = Job(
        id="job-123",
        project_id="project-456",
        job_type="generate_docx",
    )

    queue.publish_job(job)

    assert len(client.put_calls) == 1
    queue_id, details = client.put_calls[0]
    assert queue_id == "ocid1.queue.oc1..example"

    content = details["messages"][0]["content"]
    assert json.loads(content) == {
        "job_id": "job-123",
        "project_id": "project-456",
        "job_type": "generate_docx",
    }


def test_oci_worker_marks_database_job_failed_when_processing_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'oci-worker.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)

    def raise_processing_error(*args, **kwargs) -> None:
        raise RuntimeError("simulated OCI worker failure")

    monkeypatch.setitem(
        oci_queue_worker.JOB_PROCESSORS,
        "classify_files",
        raise_processing_error,
    )

    with session_local() as session:
        project = Project(customer_name="Vision Operations")
        session.add(project)
        session.commit()
        session.refresh(project)

        job = Job(project_id=project.id, job_type="classify_files")
        session.add(job)
        session.commit()
        job_id = job.id

        with pytest.raises(RuntimeError, match="simulated OCI worker failure"):
            oci_queue_worker.process_job_by_id(session, job_id, sleep_seconds=0)

        session.refresh(job)
        assert job.status == "failed"
        assert "simulated OCI worker failure" in (job.message or "")

    Base.metadata.drop_all(bind=engine)
    engine.dispose()

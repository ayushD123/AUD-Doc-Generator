import json
from types import SimpleNamespace

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


class FakeOCIQueueWorkerClient:
    def __init__(self, messages: list[object]) -> None:
        self.messages = messages
        self.deleted_receipts: list[str] = []

    def get_messages(
        self,
        queue_id: str,
        limit: int,
        visibility_in_seconds: int,
    ) -> SimpleNamespace:
        return SimpleNamespace(data=SimpleNamespace(messages=self.messages[:limit]))

    def delete_message(self, queue_id: str, message_receipt: str) -> None:
        self.deleted_receipts.append(message_receipt)


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


def test_oci_worker_deletes_stale_message_and_continues_processing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'oci-worker-stale.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(oci_queue_worker, "SessionLocal", session_local)
    monkeypatch.setattr(oci_queue_worker, "create_db_and_tables", lambda: None)

    def complete_job(session, job, sleep_seconds=0) -> None:
        job.status = "completed"
        job.progress = 100
        job.message = "Processed by fake worker."
        session.commit()

    monkeypatch.setitem(
        oci_queue_worker.JOB_PROCESSORS,
        "classify_files",
        complete_job,
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

    stale_message = SimpleNamespace(
        content=json.dumps(
            {
                "job_id": "missing-job-id",
                "project_id": "project-123",
                "job_type": "classify_files",
            }
        ),
        receipt="stale-receipt",
    )
    valid_message = SimpleNamespace(
        content=json.dumps(
            {
                "job_id": job_id,
                "project_id": project.id,
                "job_type": "classify_files",
            }
        ),
        receipt="valid-receipt",
    )
    client = FakeOCIQueueWorkerClient([stale_message, valid_message])

    try:
        processed_count = oci_queue_worker.process_oci_queue_messages(
            client=client,
            settings=Settings(
                JOB_QUEUE_BACKEND="oci",
                OCI_QUEUE_OCID="ocid1.queue.oc1..example",
            ),
            sleep_seconds=0,
        )

        with session_local() as session:
            job = session.get(Job, job_id)
            assert job is not None
            assert processed_count == 1
            assert job.status == "completed"
            assert client.deleted_receipts == ["stale-receipt", "valid-receipt"]
            assert stale_message.skip_reason == "Job missing-job-id not found."
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_oci_worker_keeps_message_when_processing_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'oci-worker-retry.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(oci_queue_worker, "SessionLocal", session_local)
    monkeypatch.setattr(oci_queue_worker, "create_db_and_tables", lambda: None)

    def fail_job(session, job, sleep_seconds=0) -> None:
        raise RuntimeError("transient processor failure")

    monkeypatch.setitem(
        oci_queue_worker.JOB_PROCESSORS,
        "classify_files",
        fail_job,
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

    message = SimpleNamespace(
        content=json.dumps(
            {
                "job_id": job_id,
                "project_id": project.id,
                "job_type": "classify_files",
            }
        ),
        receipt="retry-receipt",
    )
    client = FakeOCIQueueWorkerClient([message])

    try:
        with pytest.raises(RuntimeError, match="transient processor failure"):
            oci_queue_worker.process_oci_queue_messages(
                client=client,
                settings=Settings(
                    JOB_QUEUE_BACKEND="oci",
                    OCI_QUEUE_OCID="ocid1.queue.oc1..example",
                ),
                sleep_seconds=0,
            )

        with session_local() as session:
            job = session.get(Job, job_id)
            assert job is not None
            assert job.status == "failed"
            assert "transient processor failure" in (job.message or "")
            assert client.deleted_receipts == []
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

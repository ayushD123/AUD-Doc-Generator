from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.workers.local_worker as local_worker
from app.db.base import Base
from app.models import Job, Project, UploadedFile
from app.workers.local_worker import classify_file_type, process_classify_files_job


def test_classify_file_type_maps_extensions() -> None:
    assert classify_file_type("design.docx") == "docx"
    assert classify_file_type("slides.pptx") == "pptx"
    assert classify_file_type("config.xlsx") == "spreadsheet"
    assert classify_file_type("macro.xlsm") == "spreadsheet"
    assert classify_file_type("transcript.txt") == "transcript_text"
    assert classify_file_type("session.m4a") == "media"
    assert classify_file_type("session.mp4") == "media"
    assert classify_file_type("sample.pdf") == "pdf"
    assert classify_file_type("unknown.bin") is None


def test_process_classify_files_job_updates_job_and_uploaded_files(tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'worker.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)

    with session_local() as session:
        project = Project(customer_name="Vision Operations")
        session.add(project)
        session.commit()
        session.refresh(project)

        uploaded_file = UploadedFile(
            project_id=project.id,
            original_filename="session.mp4",
            storage_path=f"projects/{project.id}/uploads/session.mp4",
            source_role="kt_session",
        )
        job = Job(project_id=project.id, job_type="classify_files")
        session.add_all([uploaded_file, job])
        session.commit()
        session.refresh(job)
        session.refresh(uploaded_file)

        process_classify_files_job(session, job, sleep_seconds=0)

        session.refresh(job)
        session.refresh(uploaded_file)
        assert job.status == "completed"
        assert job.progress == 100
        assert uploaded_file.file_type == "media"

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_process_pending_jobs_marks_failed_job_and_retries_running_status(
    monkeypatch,
    tmp_path,
) -> None:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'worker-failure.db').as_posix()}",
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
        raise RuntimeError("simulated extraction failure")

    monkeypatch.setattr(local_worker, "SessionLocal", session_local)
    monkeypatch.setattr(local_worker, "create_db_and_tables", lambda: None)
    monkeypatch.setattr(
        local_worker,
        "process_classify_files_job",
        raise_processing_error,
    )

    with session_local() as session:
        project = Project(customer_name="Vision Operations")
        session.add(project)
        session.commit()
        session.refresh(project)

        job = Job(
            project_id=project.id,
            job_type="classify_files",
            status="running",
            progress=10,
        )
        session.add(job)
        session.commit()
        job_id = job.id

    try:
        processed_count = local_worker.process_pending_jobs(sleep_seconds=0)

        with session_local() as session:
            job = session.get(Job, job_id)
            assert job is not None
            assert processed_count == 1
            assert job.status == "failed"
            assert "simulated extraction failure" in (job.message or "")
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

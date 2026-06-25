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
    assert classify_file_type("scan.png") == "image"
    assert classify_file_type("session.mp3") == "media"
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


def test_process_pending_jobs_respects_max_jobs(monkeypatch, tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'worker-max-jobs.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(local_worker, "SessionLocal", session_local)
    monkeypatch.setattr(local_worker, "create_db_and_tables", lambda: None)

    try:
        with session_local() as session:
            project = Project(customer_name="Vision Operations")
            session.add(project)
            session.commit()
            session.refresh(project)

            uploaded_file = UploadedFile(
                project_id=project.id,
                original_filename="fdd.docx",
                storage_path=f"projects/{project.id}/uploads/fdd.docx",
                source_role="fdd",
            )
            jobs = [
                Job(project_id=project.id, job_type="classify_files"),
                Job(project_id=project.id, job_type="classify_files"),
            ]
            session.add(uploaded_file)
            session.add_all(jobs)
            session.commit()

        processed_count = local_worker.process_pending_jobs(
            sleep_seconds=0,
            max_jobs=1,
        )

        with session_local() as session:
            statuses = [
                job.status
                for job in session.query(Job).order_by(Job.created_at.asc()).all()
            ]
            assert processed_count == 1
            assert statuses.count("completed") == 1
            assert statuses.count("pending") == 1
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_run_worker_loop_polls_until_max_iterations(monkeypatch) -> None:
    processed_counts = [0, 2, 0]
    poll_intervals: list[float] = []

    def fake_process_pending_jobs(sleep_seconds=0.2, max_jobs=None) -> int:
        return processed_counts.pop(0)

    monkeypatch.setattr(local_worker, "process_pending_jobs", fake_process_pending_jobs)
    monkeypatch.setattr(local_worker, "sleep", poll_intervals.append)

    total_processed = local_worker.run_worker_loop(
        poll_interval_seconds=0.5,
        sleep_seconds=0,
        max_iterations=3,
    )

    assert total_processed == 2
    assert processed_counts == []
    assert poll_intervals == [0.5, 0.5]


def test_main_runs_one_processing_pass_by_default(monkeypatch, capsys) -> None:
    calls: list[tuple[float, int | None]] = []

    def fake_process_pending_jobs(sleep_seconds=0.2, max_jobs=None) -> int:
        calls.append((sleep_seconds, max_jobs))
        return 3

    monkeypatch.setattr(local_worker, "process_pending_jobs", fake_process_pending_jobs)

    local_worker.main([])

    assert calls == [(0.2, None)]
    assert "Processed 3 pending job(s)." in capsys.readouterr().out


def test_main_runs_loop_when_requested(monkeypatch, capsys) -> None:
    calls: list[dict[str, float | int | None]] = []

    def fake_run_worker_loop(
        poll_interval_seconds=None,
        sleep_seconds=0.2,
        max_iterations=None,
        max_jobs=None,
    ) -> int:
        calls.append(
            {
                "poll_interval_seconds": poll_interval_seconds,
                "sleep_seconds": sleep_seconds,
                "max_iterations": max_iterations,
                "max_jobs": max_jobs,
            }
        )
        return 4

    monkeypatch.setattr(local_worker, "run_worker_loop", fake_run_worker_loop)

    local_worker.main(
        [
            "--loop",
            "--poll-interval-seconds",
            "0.25",
            "--sleep-seconds",
            "0",
            "--max-iterations",
            "1",
            "--max-jobs",
            "2",
        ]
    )

    assert calls == [
        {
            "poll_interval_seconds": 0.25,
            "sleep_seconds": 0,
            "max_iterations": 1,
            "max_jobs": 2,
        }
    ]
    output = capsys.readouterr().out
    assert "Starting local worker loop." in output
    assert "Processed 4 pending job(s)" in output


def test_main_exits_cleanly_for_invalid_worker_options() -> None:
    try:
        local_worker.main(["--max-jobs", "0"])
    except SystemExit as error:
        assert str(error) == "max_jobs must be at least 1 when provided."
    else:
        raise AssertionError("Expected invalid worker options to stop the CLI.")

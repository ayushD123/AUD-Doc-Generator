from pathlib import Path

from sqlalchemy import create_engine, inspect, text

import app.db.session as db_session


def test_sqlite_schema_compatibility_adds_new_local_columns(
    monkeypatch,
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{(tmp_path / 'compat.db').as_posix()}")
    monkeypatch.setattr(db_session, "engine", engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE open_points (
                    id VARCHAR(36) PRIMARY KEY,
                    project_id VARCHAR(36) NOT NULL,
                    topic VARCHAR(500) NOT NULL,
                    question TEXT NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    source_file_id VARCHAR(36),
                    source_content_id VARCHAR(36),
                    evidence TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE TABLE generated_documents (
                    id VARCHAR(36) PRIMARY KEY,
                    project_id VARCHAR(36) NOT NULL,
                    filename VARCHAR(500) NOT NULL,
                    storage_path VARCHAR(1000) NOT NULL,
                    document_type VARCHAR(100) NOT NULL,
                    created_at DATETIME NOT NULL
                )
                """
            )
        )

    db_session.ensure_sqlite_schema_compatibility()

    inspector = inspect(engine)
    open_point_columns = {
        column["name"] for column in inspector.get_columns("open_points")
    }
    generated_document_columns = {
        column["name"] for column in inspector.get_columns("generated_documents")
    }

    assert "source_type" in open_point_columns
    assert "refinement_status" in open_point_columns
    assert "raw_source_open_point_ids_json" in open_point_columns
    assert "metadata_json" in generated_document_columns

    engine.dispose()

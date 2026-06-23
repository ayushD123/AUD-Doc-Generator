from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.database_url import build_database_engine_config, log_database_startup
from app.db.base import Base

settings = get_settings()
database_engine_config = build_database_engine_config(settings)

log_database_startup(database_engine_config)
engine = create_engine(
    database_engine_config.url,
    connect_args=database_engine_config.connect_args,
    **database_engine_config.engine_args,
)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


SQLITE_COMPATIBILITY_COLUMNS = {
    "open_points": [
        (
            "source_type",
            "VARCHAR(50) NOT NULL DEFAULT 'raw_extracted'",
        ),
        (
            "refinement_status",
            "VARCHAR(50) NOT NULL DEFAULT 'pending'",
        ),
        ("raw_source_open_point_ids_json", "TEXT"),
    ],
    "generated_documents": [
        ("metadata_json", "TEXT"),
    ],
}


def ensure_sqlite_schema_compatibility() -> None:
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table_name, columns in SQLITE_COMPATIBILITY_COLUMNS.items():
            if table_name not in table_names:
                continue

            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for column_name, column_definition in columns:
                if column_name in existing_columns:
                    continue

                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        f"ADD COLUMN {column_name} {column_definition}"
                    )
                )


def create_db_and_tables() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema_compatibility()


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session

from sqlalchemy import create_engine
from sqlalchemy.dialects import oracle
from sqlalchemy.schema import CreateIndex, CreateTable

import app.models  # noqa: F401
from app.db.base import Base


def test_models_create_against_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:")

    Base.metadata.create_all(bind=engine)

    assert Base.metadata.sorted_tables


def test_models_compile_for_oracle_without_connection() -> None:
    dialect = oracle.dialect()

    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect))

        assert table.name == table.name.lower()
        assert "VARCHAR2" in ddl or "CLOB" in ddl or "INTEGER" in ddl

    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            assert index.name is not None
            assert len(index.name) <= 30
            str(CreateIndex(index).compile(dialect=dialect))


def test_large_text_and_timestamp_columns_use_oracle_compatible_types() -> None:
    dialect = oracle.dialect()
    ddl_by_table = {
        table.name: str(CreateTable(table).compile(dialect=dialect))
        for table in Base.metadata.sorted_tables
    }

    assert "text_content CLOB" in ddl_by_table["extracted_contents"]
    assert "json_content CLOB" in ddl_by_table["extracted_contents"]
    assert "plan_json CLOB" in ddl_by_table["aud_plans"]
    assert "metadata_json CLOB" in ddl_by_table["generated_documents"]
    assert "created_at TIMESTAMP WITH TIME ZONE" in ddl_by_table["projects"]
    assert "updated_at TIMESTAMP WITH TIME ZONE" in ddl_by_table["projects"]

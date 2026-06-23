import json
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import new_uuid, utc_now
from app.db.session import database_engine_config, engine
from app.models.aud_generation_run import AUDGenerationRun
from app.models.aud_plan import AUDPlan
from app.models.extracted_content import ExtractedContent
from app.models.generated_document import GeneratedDocument
from app.models.job import Job
from app.models.project import Project
from app.models.uploaded_file import UploadedFile


@dataclass
class SmokeTestResult:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed

    def pass_step(self, message: str) -> None:
        self.passed.append(message)

    def fail_step(self, message: str) -> None:
        self.failed.append(message)


def run_smoke_test(
    session_factory: Callable[[], Session],
    provider: str,
    dialect: str,
    cleanup: bool = True,
) -> SmokeTestResult:
    result = SmokeTestResult()
    if provider != "oracle":
        result.fail_step(f"DB provider must be oracle for this smoke test; got {provider}.")
        return result

    project_id: str | None = None
    unique_suffix = new_uuid()
    now = utc_now()
    metadata = {
        "smoke_test": True,
        "dialect": dialect,
        "nested": {"large_text_chars": 5000, "unicode_safe": "oracle"},
    }
    large_text = "Oracle smoke test CLOB payload. " * 200

    with session_factory() as session:
        try:
            project = Project(
                name=f"oracle-smoke-{unique_suffix}",
                customer_name="Oracle Smoke Test",
                module_name="AUD Generator",
                email_id="oracle-smoke@example.com",
                status="draft",
            )
            session.add(project)
            session.flush()
            project_id = project.id
            result.pass_step("created project")

            uploaded_file = UploadedFile(
                project_id=project.id,
                original_filename="oracle-smoke-fdd.txt",
                file_type="transcript_text",
                storage_path=f"projects/{project.id}/uploads/oracle-smoke-fdd.txt",
                source_role="fdd",
            )
            session.add(uploaded_file)
            session.flush()
            result.pass_step("created uploaded file metadata")

            job = Job(
                project_id=project.id,
                job_type="generate_aud",
                status="completed",
                progress=100,
                message=large_text,
            )
            session.add(job)
            result.pass_step("created job")

            extracted_content = ExtractedContent(
                project_id=project.id,
                uploaded_file_id=uploaded_file.id,
                content_type="transcript_text",
                title="Oracle Smoke Extracted Content",
                text_content=large_text,
                json_content=json.dumps(metadata),
            )
            session.add(extracted_content)
            result.pass_step("inserted representative CLOB and JSON content")

            aud_plan = AUDPlan(
                project_id=project.id,
                status="draft",
                plan_json=json.dumps(
                    {
                        "sections": [
                            {
                                "id": "purpose",
                                "title": "Purpose and Scope",
                                "include": True,
                            }
                        ],
                        "source": "oracle_smoke_test",
                    }
                ),
            )
            session.add(aud_plan)
            result.pass_step("inserted AUD plan JSON")

            generated_document = GeneratedDocument(
                project_id=project.id,
                filename="oracle-smoke-aud.docx",
                storage_path=f"projects/{project.id}/outputs/oracle-smoke-aud.docx",
                document_type="aud_docx",
                metadata_json=json.dumps(metadata),
            )
            session.add(generated_document)
            session.flush()

            generation_run = AUDGenerationRun(
                project_id=project.id,
                status="completed",
                current_stage=None,
                completed_stages_json=json.dumps(
                    ["validate_project_inputs", "generate_final_docx"]
                ),
                warnings_json="[]",
                final_document_id=generated_document.id,
                started_at=now,
                completed_at=now,
            )
            session.add(generation_run)
            result.pass_step("inserted generated document metadata and run status")

            session.commit()
        except Exception as exc:
            session.rollback()
            result.fail_step(f"insert workflow failed: {exc}")
            return result

        try:
            stored_project = session.scalar(
                select(Project).where(Project.id == project_id)
            )
            if stored_project is None:
                result.fail_step("project readback failed")
            else:
                result.pass_step("read project")

            stored_content = session.scalar(
                select(ExtractedContent).where(
                    ExtractedContent.project_id == project_id
                )
            )
            if stored_content is None or json.loads(stored_content.json_content or "{}")[
                "smoke_test"
            ] is not True:
                result.fail_step("CLOB/JSON readback failed")
            else:
                result.pass_step("read CLOB/JSON content")

            documents = list(
                session.scalars(
                    select(GeneratedDocument)
                    .where(GeneratedDocument.project_id == project_id)
                    .order_by(GeneratedDocument.created_at.desc())
                )
            )
            if not documents:
                result.fail_step("generated document list readback failed")
            else:
                result.pass_step("read generated document list")

            stored_run = session.scalar(
                select(AUDGenerationRun).where(
                    AUDGenerationRun.project_id == project_id
                )
            )
            if stored_run is None or stored_run.completed_at is None:
                result.fail_step("generation run datetime readback failed")
            else:
                result.pass_step("read generation run timestamps")
        except Exception as exc:
            result.fail_step(f"readback workflow failed: {exc}")
        finally:
            if cleanup and project_id:
                try:
                    project = session.scalar(select(Project).where(Project.id == project_id))
                    if project is not None:
                        session.delete(project)
                        session.commit()
                    result.pass_step("cleaned up smoke test records")
                except Exception as exc:
                    session.rollback()
                    result.fail_step(f"cleanup failed for project {project_id}: {exc}")

    return result


def _print_summary(result: SmokeTestResult, provider: str, dialect: str) -> None:
    print(f"provider: {provider}")
    print(f"dialect: {dialect}")
    print(f"status: {'ok' if result.ok else 'error'}")
    for message in result.passed:
        print(f"PASS: {message}")
    for message in result.failed:
        print(f"FAIL: {message}")


def main() -> int:
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    result = run_smoke_test(
        session_factory=session_factory,
        provider=database_engine_config.provider,
        dialect=engine.dialect.name,
    )
    _print_summary(result, database_engine_config.provider, engine.dialect.name)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from traceback import format_exception_only

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.models import AUDGenerationRun, GeneratedDocument, Job, Project, UploadedFile

logger = logging.getLogger(__name__)

StageProcessor = Callable[[Session, Job], None]


class AUDPipelineStage(StrEnum):
    VALIDATE_PROJECT_INPUTS = "validate_project_inputs"
    EXTRACT_CONTENT = "extract_content"
    ENRICH_DOCUMENT_UNDERSTANDING = "enrich_document_understanding"
    TRANSCRIBE_MEDIA = "transcribe_media"
    GENERATE_INITIAL_AUD_PLAN = "generate_initial_aud_plan"
    BUILD_EVIDENCE_INDEX = "build_evidence_index"
    GENERATE_SOURCE_SUMMARIES_AI = "generate_source_summaries_ai"
    ENHANCE_AUD_PLAN_AI = "enhance_aud_plan_ai"
    BUILD_SECTION_EVIDENCE_PACKS = "build_section_evidence_packs"
    GENERATE_OPEN_POINTS_AI = "generate_open_points_ai"
    GENERATE_SECTION_DRAFTS_AI = "generate_section_drafts_ai"
    GENERATE_FINAL_DOCX = "generate_final_docx"
    FINALIZE_ARTIFACT = "finalize_artifact"


AUD_PIPELINE_STAGES: list[AUDPipelineStage] = [
    AUDPipelineStage.VALIDATE_PROJECT_INPUTS,
    AUDPipelineStage.EXTRACT_CONTENT,
    AUDPipelineStage.ENRICH_DOCUMENT_UNDERSTANDING,
    AUDPipelineStage.TRANSCRIBE_MEDIA,
    AUDPipelineStage.GENERATE_INITIAL_AUD_PLAN,
    AUDPipelineStage.BUILD_EVIDENCE_INDEX,
    AUDPipelineStage.GENERATE_SOURCE_SUMMARIES_AI,
    AUDPipelineStage.ENHANCE_AUD_PLAN_AI,
    AUDPipelineStage.BUILD_SECTION_EVIDENCE_PACKS,
    AUDPipelineStage.GENERATE_OPEN_POINTS_AI,
    AUDPipelineStage.GENERATE_SECTION_DRAFTS_AI,
    AUDPipelineStage.GENERATE_FINAL_DOCX,
    AUDPipelineStage.FINALIZE_ARTIFACT,
]

INTERNAL_STAGE_JOB_TYPES: dict[AUDPipelineStage, list[str]] = {
    AUDPipelineStage.VALIDATE_PROJECT_INPUTS: ["classify_files"],
    AUDPipelineStage.EXTRACT_CONTENT: ["extract_all"],
    AUDPipelineStage.ENRICH_DOCUMENT_UNDERSTANDING: [
        "enrich_with_document_understanding"
    ],
    AUDPipelineStage.TRANSCRIBE_MEDIA: ["transcribe_media"],
    AUDPipelineStage.GENERATE_INITIAL_AUD_PLAN: ["generate_aud_plan"],
    AUDPipelineStage.BUILD_EVIDENCE_INDEX: ["build_evidence_index"],
    AUDPipelineStage.GENERATE_SOURCE_SUMMARIES_AI: ["generate_source_summaries_ai"],
    AUDPipelineStage.ENHANCE_AUD_PLAN_AI: ["enhance_aud_plan_ai"],
    AUDPipelineStage.BUILD_SECTION_EVIDENCE_PACKS: ["build_section_evidence_packs"],
    AUDPipelineStage.GENERATE_OPEN_POINTS_AI: [
        "extract_open_points",
        "refine_open_points_ai",
    ],
    AUDPipelineStage.GENERATE_SECTION_DRAFTS_AI: ["generate_section_drafts_ai"],
    AUDPipelineStage.GENERATE_FINAL_DOCX: ["generate_docx"],
}

DOCUMENT_UNDERSTANDING_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
MEDIA_EXTENSIONS = {".mp3", ".m4a", ".mp4"}
COMPLETED_JOB_STATUSES = {"completed", "completed_with_warnings"}


def parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    return [str(item) for item in parsed]


def set_json_list(items: list[str]) -> str:
    return json.dumps(items)


def get_or_create_generation_run(
    session: Session,
    project_id: str,
    run_id: str | None = None,
) -> AUDGenerationRun:
    if run_id:
        existing_run = session.get(AUDGenerationRun, run_id)
        if existing_run is not None:
            return existing_run

    generation_run = (
        AUDGenerationRun(id=run_id, project_id=project_id, status="queued")
        if run_id
        else AUDGenerationRun(project_id=project_id, status="queued")
    )
    session.add(generation_run)
    session.commit()
    session.refresh(generation_run)
    return generation_run


def find_latest_generation_run(
    session: Session,
    project_id: str,
) -> AUDGenerationRun | None:
    return session.scalars(
        select(AUDGenerationRun)
        .where(AUDGenerationRun.project_id == project_id)
        .order_by(AUDGenerationRun.created_at.desc())
    ).first()


class AUDPipelineOrchestrator:
    def __init__(
        self,
        session: Session,
        generation_run: AUDGenerationRun,
        stage_processors: dict[str, StageProcessor],
    ) -> None:
        self.session = session
        self.generation_run = generation_run
        self.stage_processors = stage_processors

    def run(self) -> AUDGenerationRun:
        project = self.session.get(Project, self.generation_run.project_id)
        if project is None:
            self.mark_failed(
                AUDPipelineStage.VALIDATE_PROJECT_INPUTS,
                "Project not found.",
            )
            return self.generation_run

        self.generation_run.status = "running"
        self.generation_run.started_at = self.generation_run.started_at or utc_now()
        self.generation_run.error_message = None
        self.generation_run.failed_stage = None
        self.session.commit()

        for stage in AUD_PIPELINE_STAGES:
            completed_stages = parse_json_list(
                self.generation_run.completed_stages_json
            )
            if stage.value in completed_stages:
                continue

            try:
                self.start_stage(stage)
                self.run_stage(stage)
                self.complete_stage(stage)
            except Exception as error:
                error_message = "".join(
                    format_exception_only(type(error), error)
                ).strip()
                self.mark_failed(stage, error_message)
                return self.generation_run

        warnings = parse_json_list(self.generation_run.warnings_json)
        self.generation_run.status = "completed_with_warnings" if warnings else "completed"
        self.generation_run.current_stage = None
        self.generation_run.completed_at = utc_now()
        self.session.commit()
        return self.generation_run

    def start_stage(self, stage: AUDPipelineStage) -> None:
        logger.info("Starting AUD generation stage %s", stage.value)
        self.generation_run.current_stage = stage.value
        self.generation_run.status = "running"
        self.session.commit()

    def complete_stage(self, stage: AUDPipelineStage) -> None:
        completed_stages = parse_json_list(self.generation_run.completed_stages_json)
        if stage.value not in completed_stages:
            completed_stages.append(stage.value)
        self.generation_run.completed_stages_json = set_json_list(completed_stages)
        logger.info("Completed AUD generation stage %s", stage.value)
        self.session.commit()

    def mark_failed(self, stage: AUDPipelineStage, error_message: str) -> None:
        self.session.rollback()
        logger.error(
            "AUD generation stage %s failed for project %s",
            stage.value,
            self.generation_run.project_id,
        )
        self.generation_run.status = "failed"
        self.generation_run.current_stage = stage.value
        self.generation_run.failed_stage = stage.value
        self.generation_run.error_message = error_message
        self.generation_run.completed_at = utc_now()
        self.session.commit()

    def add_warning(self, warning: str) -> None:
        warnings = parse_json_list(self.generation_run.warnings_json)
        warnings.append(warning)
        self.generation_run.warnings_json = set_json_list(warnings)
        self.session.commit()

    def run_stage(self, stage: AUDPipelineStage) -> None:
        if stage == AUDPipelineStage.VALIDATE_PROJECT_INPUTS:
            self.validate_project_inputs()
        elif stage == AUDPipelineStage.ENRICH_DOCUMENT_UNDERSTANDING:
            if not self.has_uploaded_file_with_extension(DOCUMENT_UNDERSTANDING_EXTENSIONS):
                return
            self.run_internal_jobs(stage)
        elif stage == AUDPipelineStage.TRANSCRIBE_MEDIA:
            if not self.has_uploaded_file_with_extension(MEDIA_EXTENSIONS):
                return
            self.run_internal_jobs(stage)
        elif stage == AUDPipelineStage.FINALIZE_ARTIFACT:
            self.finalize_artifact()
        else:
            self.run_internal_jobs(stage)

    def validate_project_inputs(self) -> None:
        uploaded_files = self.list_uploaded_files()
        if not uploaded_files:
            raise ValueError("At least one uploaded source file is required.")

        self.run_internal_jobs(AUDPipelineStage.VALIDATE_PROJECT_INPUTS)

    def run_internal_jobs(self, stage: AUDPipelineStage) -> None:
        for job_type in INTERNAL_STAGE_JOB_TYPES.get(stage, []):
            processor = self.stage_processors.get(job_type)
            if processor is None:
                raise ValueError(f"No processor registered for stage job {job_type}.")

            message = f"AUD generation stage {stage.value} queued {job_type}."
            if job_type == "generate_docx":
                message = json.dumps(
                    {
                        "status_message": message,
                        "options": {
                            "use_ai_drafts": True,
                            "include_draft_sections": True,
                            "include_images": True,
                            "include_open_points": True,
                        },
                    }
                )

            stage_job = Job(
                project_id=self.generation_run.project_id,
                job_type=job_type,
                message=message,
            )
            self.session.add(stage_job)
            self.session.commit()
            self.session.refresh(stage_job)

            try:
                processor(self.session, stage_job)
            except Exception as error:
                stage_job = self.mark_stage_job_failed(stage_job.id, error)

            self.session.refresh(stage_job)
            self.handle_stage_job_result(stage, stage_job)

    def mark_stage_job_failed(self, stage_job_id: str, error: Exception) -> Job:
        self.session.rollback()
        stage_job = self.session.get(Job, stage_job_id)
        if stage_job is None:
            raise error

        stage_job.status = "failed"
        stage_job.message = "".join(format_exception_only(type(error), error)).strip()
        self.session.commit()
        self.session.refresh(stage_job)
        return stage_job

    def handle_stage_job_result(
        self,
        stage: AUDPipelineStage,
        stage_job: Job,
    ) -> None:
        if stage_job.status in COMPLETED_JOB_STATUSES:
            if stage_job.status == "completed_with_warnings":
                self.add_warning(
                    f"{stage.value}/{stage_job.job_type}: {stage_job.message or ''}"
                )
            return

        if stage_job.status == "failed":
            raise RuntimeError(stage_job.message or f"{stage_job.job_type} failed.")

        raise RuntimeError(
            f"{stage_job.job_type} ended with unexpected status {stage_job.status}."
        )

    def finalize_artifact(self) -> None:
        generated_document = self.session.scalars(
            select(GeneratedDocument)
            .where(GeneratedDocument.project_id == self.generation_run.project_id)
            .order_by(GeneratedDocument.created_at.desc())
        ).first()

        if generated_document is None:
            raise RuntimeError("Final DOCX generation did not create a document.")

        self.generation_run.final_document_id = generated_document.id
        self.session.commit()

    def list_uploaded_files(self) -> list[UploadedFile]:
        return list(
            self.session.scalars(
                select(UploadedFile).where(
                    UploadedFile.project_id == self.generation_run.project_id
                )
            )
        )

    def has_uploaded_file_with_extension(self, extensions: set[str]) -> bool:
        return any(
            Path(uploaded_file.original_filename or "").suffix.lower() in extensions
            for uploaded_file in self.list_uploaded_files()
        )

from __future__ import annotations

import json
from typing import Any, Callable, Protocol

from app.core.config import Settings, get_settings
from app.models import Job


class JobQueueService(Protocol):
    def publish_job(self, job: Job) -> None:
        ...


class LocalJobQueueService:
    def publish_job(self, job: Job) -> None:
        return None


class OCIJobQueueService:
    def __init__(
        self,
        settings: Settings | None = None,
        client: object | None = None,
        message_details_factory: Callable[[str], object] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.queue_id = self.require_setting(
            self.settings.OCI_QUEUE_OCID,
            "OCI_QUEUE_OCID",
        )
        self.client = client or self.build_client()
        self.message_details_factory = (
            message_details_factory
            or self.build_message_details_factory()
        )

    @staticmethod
    def require_setting(value: str | None, setting_name: str) -> str:
        if not value:
            raise ValueError(f"{setting_name} is required when JOB_QUEUE_BACKEND=oci.")

        return value

    def build_oci_config(self) -> dict[str, Any]:
        try:
            import oci
        except ImportError as error:
            raise RuntimeError(
                "OCI Python SDK is required when JOB_QUEUE_BACKEND=oci."
            ) from error

        config_file = self.settings.OCI_CONFIG_FILE
        profile = self.settings.OCI_PROFILE or "DEFAULT"
        config = (
            oci.config.from_file(file_location=config_file, profile_name=profile)
            if config_file
            else oci.config.from_file(profile_name=profile)
        )

        if self.settings.OCI_REGION:
            config["region"] = self.settings.OCI_REGION

        return config

    def build_client(self) -> object:
        try:
            import oci
        except ImportError as error:
            raise RuntimeError(
                "OCI Python SDK is required when JOB_QUEUE_BACKEND=oci."
            ) from error

        kwargs = {}
        if self.settings.OCI_QUEUE_ENDPOINT:
            kwargs["service_endpoint"] = self.settings.OCI_QUEUE_ENDPOINT

        return oci.queue.QueueClient(self.build_oci_config(), **kwargs)

    def build_message_details_factory(self) -> Callable[[str], object]:
        try:
            import oci
        except ImportError as error:
            raise RuntimeError(
                "OCI Python SDK is required when JOB_QUEUE_BACKEND=oci."
            ) from error

        def create_details(content: str) -> object:
            return oci.queue.models.PutMessagesDetails(
                messages=[
                    oci.queue.models.PutMessagesDetailsEntry(content=content),
                ],
            )

        return create_details

    @staticmethod
    def serialize_job(job: Job) -> str:
        return json.dumps(
            {
                "job_id": job.id,
                "project_id": job.project_id,
                "job_type": job.job_type,
            },
        )

    def publish_job(self, job: Job) -> None:
        details = self.message_details_factory(self.serialize_job(job))
        self.client.put_messages(self.queue_id, details)


def get_job_queue_service() -> JobQueueService:
    settings = get_settings()
    queue_backend = settings.JOB_QUEUE_BACKEND.strip().lower()

    if queue_backend == "local":
        return LocalJobQueueService()

    if queue_backend == "oci":
        return OCIJobQueueService(settings)

    raise ValueError("JOB_QUEUE_BACKEND must be either 'local' or 'oci'.")

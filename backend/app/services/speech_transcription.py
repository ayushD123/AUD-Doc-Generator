from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from app.core.config import Settings, get_settings
from app.models import UploadedFile


MEDIA_FILE_EXTENSIONS = {".m4a", ".mp4", ".mp3"}
TERMINAL_SPEECH_STATES = {"SUCCEEDED", "FAILED", "CANCELED", "CANCELLED"}
SPEECH_DISPLAY_NAME_MAX_LENGTH = 255


@dataclass
class SpeechTranscriptionOutput:
    speech_job_id: str
    speech_job_status: str
    model_type: str
    language_code: str
    output_prefix: str
    output_object_name: str
    transcript_text: str
    timestamps: list[dict[str, Any]]


def is_media_upload(uploaded_file: UploadedFile) -> bool:
    extension = Path(uploaded_file.original_filename).suffix.lower()
    return extension in MEDIA_FILE_EXTENSIONS


def build_speech_display_name(uploaded_file: UploadedFile) -> str:
    filename_stem = Path(uploaded_file.original_filename or "media").stem
    raw_name = f"AUD_transcript_{filename_stem}_{uploaded_file.id}"
    safe_name = "".join(
        character
        if character.isascii() and (character.isalnum() or character in {"-", "_"})
        else "_"
        for character in raw_name
    )
    safe_name = re.sub(r"_+", "_", safe_name).strip("_-")
    return (safe_name or f"AUD_transcript_{uploaded_file.id}")[
        :SPEECH_DISPLAY_NAME_MAX_LENGTH
    ]


def format_speech_output_prefix(
    template: str,
    project_id: str,
    job_id: str,
    uploaded_file_id: str,
) -> str:
    try:
        base_prefix = template.format(project_id=project_id)
    except KeyError as error:
        raise ValueError(
            "OCI_SPEECH_OUTPUT_PREFIX may only use the {project_id} placeholder."
        ) from error

    normalized_prefix = base_prefix.strip("/")
    if normalized_prefix:
        normalized_prefix = f"{normalized_prefix}/"

    return f"{normalized_prefix}{job_id}/{uploaded_file_id}/"


def collect_values_by_key(payload: Any, keys: set[str]) -> list[str]:
    values: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key.lower() in keys and isinstance(value, str) and value.strip():
                    values.append(value.strip())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return values


def deduplicate_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduplicated: list[str] = []

    for value in values:
        normalized = " ".join(value.split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduplicated.append(value)

    return deduplicated


def extract_transcript_text(payload: dict[str, Any] | list[Any]) -> str:
    transcript_values = collect_values_by_key(payload, {"transcription", "transcript"})
    if not transcript_values:
        transcript_values = collect_values_by_key(payload, {"text"})

    return "\n\n".join(deduplicate_preserving_order(transcript_values)).strip()


def collect_timestamps(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    timestamps: list[dict[str, Any]] = []

    def first_present(node: dict[str, Any], names: tuple[str, ...]) -> Any:
        for name in names:
            if name in node:
                return node[name]
        return None

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            start_time = first_present(node, ("startTime", "start_time", "start"))
            end_time = first_present(node, ("endTime", "end_time", "end"))
            token = first_present(node, ("token", "word", "text"))

            if start_time is not None or end_time is not None:
                timestamps.append(
                    {
                        "token": token,
                        "start_time": start_time,
                        "end_time": end_time,
                    }
                )

            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return timestamps


class OCISpeechTranscriptionService:
    def __init__(
        self,
        settings: Settings | None = None,
        speech_client: object | None = None,
        object_storage_client: object | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.namespace = self.require_setting(
            self.settings.OCI_NAMESPACE,
            "OCI_NAMESPACE",
        )
        self.input_bucket = self.require_setting(
            self.settings.OCI_BUCKET_NAME,
            "OCI_BUCKET_NAME",
        )
        self.compartment_id = self.require_setting(
            self.settings.OCI_SPEECH_COMPARTMENT_OCID,
            "OCI_SPEECH_COMPARTMENT_OCID",
        )
        self.output_bucket = self.require_setting(
            self.settings.OCI_SPEECH_OUTPUT_BUCKET,
            "OCI_SPEECH_OUTPUT_BUCKET",
        )
        self.speech_client = speech_client or self.build_speech_client()
        self.object_storage_client = (
            object_storage_client or self.build_object_storage_client()
        )

    @staticmethod
    def require_setting(value: str | None, setting_name: str) -> str:
        if not value:
            raise ValueError(f"{setting_name} is required for OCI Speech transcription.")

        return value

    def build_oci_config(self) -> dict[str, Any]:
        try:
            import oci
        except ImportError as error:
            raise RuntimeError("OCI Python SDK is required for OCI Speech.") from error

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

    def build_speech_client(self) -> object:
        try:
            import oci
        except ImportError as error:
            raise RuntimeError("OCI Python SDK is required for OCI Speech.") from error

        return oci.ai_speech.AIServiceSpeechClient(self.build_oci_config())

    def build_object_storage_client(self) -> object:
        try:
            import oci
        except ImportError as error:
            raise RuntimeError("OCI Python SDK is required for OCI Speech.") from error

        return oci.object_storage.ObjectStorageClient(self.build_oci_config())

    def ensure_input_object_exists(self, object_name: str) -> None:
        self.object_storage_client.head_object(
            self.namespace,
            self.input_bucket,
            object_name,
        )

    def submit_transcription_job(
        self,
        uploaded_file: UploadedFile,
        output_prefix: str,
    ) -> str:
        try:
            import oci
        except ImportError as error:
            raise RuntimeError("OCI Python SDK is required for OCI Speech.") from error

        self.ensure_input_object_exists(uploaded_file.storage_path)
        models = oci.ai_speech.models
        request = models.CreateTranscriptionJobDetails(
            display_name=build_speech_display_name(uploaded_file),
            compartment_id=self.compartment_id,
            input_location=models.ObjectListInlineInputLocation(
                location_type=(
                    models.ObjectListInlineInputLocation
                    .LOCATION_TYPE_OBJECT_LIST_INLINE_INPUT_LOCATION
                ),
                object_locations=[
                    models.ObjectLocation(
                        namespace_name=self.namespace,
                        bucket_name=self.input_bucket,
                        object_names=[uploaded_file.storage_path],
                    )
                ],
            ),
            output_location=models.OutputLocation(
                namespace_name=self.namespace,
                bucket_name=self.output_bucket,
                prefix=output_prefix,
            ),
            model_details=models.TranscriptionModelDetails(
                model_type=self.settings.OCI_SPEECH_MODEL_TYPE,
                language_code=self.settings.OCI_SPEECH_LANGUAGE_CODE,
            ),
            freeform_tags={
                "project_id": uploaded_file.project_id,
                "uploaded_file_id": uploaded_file.id,
            },
        )
        response = self.speech_client.create_transcription_job(request)
        speech_job_id = getattr(response.data, "id", None)
        if not speech_job_id:
            raise RuntimeError("OCI Speech did not return a transcription job OCID.")

        return speech_job_id

    def wait_for_completion(
        self,
        speech_job_id: str,
        timeout_seconds: int,
        poll_interval_seconds: float,
    ) -> str:
        deadline = monotonic() + timeout_seconds

        while True:
            response = self.speech_client.get_transcription_job(speech_job_id)
            status = str(getattr(response.data, "lifecycle_state", "")).upper()

            if status in TERMINAL_SPEECH_STATES:
                return status

            if monotonic() >= deadline:
                raise TimeoutError(
                    f"OCI Speech transcription job {speech_job_id} timed out."
                )

            sleep(max(poll_interval_seconds, 0.1))

    def list_output_json_objects(self, output_prefix: str) -> list[str]:
        response = self.object_storage_client.list_objects(
            self.namespace,
            self.output_bucket,
            prefix=output_prefix,
        )
        objects = getattr(response.data, "objects", [])
        object_names = [getattr(item, "name", "") for item in objects]
        return sorted(
            object_name
            for object_name in object_names
            if object_name.lower().endswith(".json")
        )

    def read_json_object(self, object_name: str) -> dict[str, Any] | list[Any]:
        response = self.object_storage_client.get_object(
            self.namespace,
            self.output_bucket,
            object_name,
        )
        content = response.data.content
        if isinstance(content, bytes):
            content = content.decode("utf-8")

        return json.loads(content)

    def read_transcription_output(
        self,
        speech_job_id: str,
        speech_job_status: str,
        output_prefix: str,
    ) -> SpeechTranscriptionOutput:
        output_object_names = self.list_output_json_objects(output_prefix)
        if not output_object_names:
            raise FileNotFoundError(
                f"No OCI Speech JSON output found under {output_prefix}."
            )

        for output_object_name in output_object_names:
            raw_json = self.read_json_object(output_object_name)
            transcript_text = extract_transcript_text(raw_json)
            if transcript_text:
                return SpeechTranscriptionOutput(
                    speech_job_id=speech_job_id,
                    speech_job_status=speech_job_status,
                    model_type=self.settings.OCI_SPEECH_MODEL_TYPE,
                    language_code=self.settings.OCI_SPEECH_LANGUAGE_CODE,
                    output_prefix=output_prefix,
                    output_object_name=output_object_name,
                    transcript_text=transcript_text,
                    timestamps=collect_timestamps(raw_json),
                )

        raise ValueError("OCI Speech output did not contain transcript text.")

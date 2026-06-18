import json
import re
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.workers.local_worker as local_worker
from app.core.config import Settings
from app.db.base import Base
from app.models import ExtractedContent, Job, Project, UploadedFile
from app.services.speech_transcription import (
    OCISpeechTranscriptionService,
    SpeechTranscriptionOutput,
    build_speech_display_name,
)
from app.workers.local_worker import process_transcribe_media_job


class FakeSpeechClient:
    def __init__(self) -> None:
        self.created_details = None

    def create_transcription_job(self, create_transcription_job_details):
        self.created_details = create_transcription_job_details
        return SimpleNamespace(data=SimpleNamespace(id="ocid1.speechjob.oc1..test"))

    def get_transcription_job(self, transcription_job_id: str):
        return SimpleNamespace(data=SimpleNamespace(lifecycle_state="SUCCEEDED"))


class FakeObjectStorageClient:
    def __init__(self) -> None:
        self.head_calls: list[tuple[str, str, str]] = []
        self.objects = {
            "projects/project-123/speech/job-123/file-456/output.json": json.dumps(
                {
                    "transcriptions": [
                        {
                            "transcription": "Welcome to the KT session.",
                            "tokens": [
                                {
                                    "token": "Welcome",
                                    "startTime": "0.0",
                                    "endTime": "0.4",
                                }
                            ],
                        }
                    ]
                }
            ).encode("utf-8")
        }

    def head_object(self, namespace: str, bucket_name: str, object_name: str) -> None:
        self.head_calls.append((namespace, bucket_name, object_name))

    def list_objects(self, namespace: str, bucket_name: str, prefix: str):
        matching_objects = [
            SimpleNamespace(name=object_name)
            for object_name in self.objects
            if object_name.startswith(prefix)
        ]
        return SimpleNamespace(data=SimpleNamespace(objects=matching_objects))

    def get_object(self, namespace: str, bucket_name: str, object_name: str):
        return SimpleNamespace(
            data=SimpleNamespace(content=self.objects[object_name])
        )


class FakeSpeechTranscriptionService:
    def __init__(self) -> None:
        self.submitted_prefixes: list[str] = []

    def submit_transcription_job(
        self,
        uploaded_file: UploadedFile,
        output_prefix: str,
    ) -> str:
        self.submitted_prefixes.append(output_prefix)
        return "ocid1.speechjob.oc1..worker"

    def wait_for_completion(
        self,
        speech_job_id: str,
        timeout_seconds: int,
        poll_interval_seconds: float,
    ) -> str:
        return "SUCCEEDED"

    def read_transcription_output(
        self,
        speech_job_id: str,
        speech_job_status: str,
        output_prefix: str,
    ) -> SpeechTranscriptionOutput:
        return SpeechTranscriptionOutput(
            speech_job_id=speech_job_id,
            speech_job_status=speech_job_status,
            model_type="WHISPER_MEDIUM",
            language_code="en",
            output_prefix=output_prefix,
            output_object_name=f"{output_prefix}output.json",
            transcript_text="Transcribed media content.",
            timestamps=[
                {
                    "token": "Transcribed",
                    "start_time": "0.0",
                    "end_time": "0.5",
                }
            ],
        )


def test_oci_speech_service_submits_and_reads_transcription_output() -> None:
    speech_client = FakeSpeechClient()
    object_storage_client = FakeObjectStorageClient()
    service = OCISpeechTranscriptionService(
        settings=Settings(
            STORAGE_BACKEND="oci",
            OCI_NAMESPACE="tenantnamespace",
            OCI_BUCKET_NAME="aud-input",
            OCI_SPEECH_COMPARTMENT_OCID="ocid1.compartment.oc1..test",
            OCI_SPEECH_OUTPUT_BUCKET="aud-speech-output",
            OCI_SPEECH_MODEL_TYPE="WHISPER_MEDIUM",
            OCI_SPEECH_LANGUAGE_CODE="en",
        ),
        speech_client=speech_client,
        object_storage_client=object_storage_client,
    )
    uploaded_file = UploadedFile(
        id="file-456",
        project_id="project-123",
        original_filename="JM HUBER KT Session (3).m4a",
        file_type="media",
        storage_path="projects/project-123/uploads/file-456_JM HUBER KT Session (3).m4a",
        source_role="kt_session",
    )
    output_prefix = "projects/project-123/speech/job-123/file-456/"

    speech_job_id = service.submit_transcription_job(uploaded_file, output_prefix)
    status = service.wait_for_completion(speech_job_id, 1, 0)
    output = service.read_transcription_output(speech_job_id, status, output_prefix)

    assert speech_job_id == "ocid1.speechjob.oc1..test"
    assert status == "SUCCEEDED"
    assert object_storage_client.head_calls == [
        (
            "tenantnamespace",
            "aud-input",
            "projects/project-123/uploads/file-456_JM HUBER KT Session (3).m4a",
        )
    ]
    assert re.fullmatch(r"[A-Za-z0-9_-]+", speech_client.created_details.display_name)
    assert speech_client.created_details.display_name == (
        "AUD_transcript_JM_HUBER_KT_Session_3_file-456"
    )
    assert speech_client.created_details.compartment_id == (
        "ocid1.compartment.oc1..test"
    )
    assert speech_client.created_details.output_location.bucket_name == (
        "aud-speech-output"
    )
    assert speech_client.created_details.model_details.model_type == "WHISPER_MEDIUM"
    assert speech_client.created_details.model_details.language_code == "en"
    assert output.model_type == "WHISPER_MEDIUM"
    assert output.language_code == "en"
    assert output.transcript_text == "Welcome to the KT session."
    assert output.timestamps == [
        {
            "token": "Welcome",
            "start_time": "0.0",
            "end_time": "0.4",
        }
    ]


def test_speech_display_name_allows_only_oci_supported_characters() -> None:
    uploaded_file = UploadedFile(
        id="file-789",
        project_id="project-123",
        original_filename="KT Session.final (v2).mp4",
        file_type="media",
        storage_path="projects/project-123/uploads/file-789_KT Session.final (v2).mp4",
        source_role="kt_session",
    )

    display_name = build_speech_display_name(uploaded_file)

    assert display_name == "AUD_transcript_KT_Session_final_v2_file-789"
    assert re.fullmatch(r"[A-Za-z0-9_-]+", display_name)


def test_transcribe_media_worker_stores_extracted_transcript(
    monkeypatch,
    tmp_path,
) -> None:
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'speech-worker.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)
    fake_service = FakeSpeechTranscriptionService()
    monkeypatch.setattr(
        local_worker,
        "get_settings",
        lambda: Settings(
            STORAGE_BACKEND="oci",
            OCI_NAMESPACE="tenantnamespace",
            OCI_BUCKET_NAME="aud-input",
            OCI_SPEECH_COMPARTMENT_OCID="ocid1.compartment.oc1..test",
            OCI_SPEECH_OUTPUT_BUCKET="aud-speech-output",
            OCI_SPEECH_MODEL_TYPE="WHISPER_MEDIUM",
            OCI_SPEECH_LANGUAGE_CODE="en",
            OCI_SPEECH_TIMEOUT_SECONDS=1,
            OCI_SPEECH_POLL_INTERVAL_SECONDS=0,
        ),
    )

    with session_local() as session:
        project = Project(customer_name="Vision Operations")
        session.add(project)
        session.commit()
        session.refresh(project)

        uploaded_file = UploadedFile(
            project_id=project.id,
            original_filename="kt-session.mp3",
            file_type="media",
            storage_path=f"projects/{project.id}/uploads/kt-session.mp3",
            source_role="kt_session",
        )
        job = Job(project_id=project.id, job_type="transcribe_media")
        session.add_all([uploaded_file, job])
        session.commit()
        session.refresh(job)
        session.refresh(uploaded_file)

        process_transcribe_media_job(
            session,
            job,
            sleep_seconds=0,
            speech_service=fake_service,
        )
        session.refresh(job)

        extracted_content = session.scalar(select(ExtractedContent))
        assert extracted_content is not None
        assert job.status == "completed"
        assert job.progress == 100
        assert job.message == "Transcribed 1 media file(s)."
        assert extracted_content.project_id == project.id
        assert extracted_content.uploaded_file_id == uploaded_file.id
        assert extracted_content.content_type == "transcript"
        assert extracted_content.title == "kt-session.mp3 transcript"
        assert extracted_content.text_content == "Transcribed media content."

        json_content = json.loads(extracted_content.json_content or "{}")
        assert json_content["speech_job_id"] == "ocid1.speechjob.oc1..worker"
        assert json_content["speech_job_status"] == "SUCCEEDED"
        assert json_content["speech_model_type"] == "WHISPER_MEDIUM"
        assert json_content["speech_language_code"] == "en"
        assert json_content["source_media_file_id"] == uploaded_file.id
        assert json_content["timestamps"] == [
            {
                "token": "Transcribed",
                "start_time": "0.0",
                "end_time": "0.5",
            }
        ]
        assert fake_service.submitted_prefixes == [
            f"projects/{project.id}/speech/{job.id}/{uploaded_file.id}/"
        ]

    Base.metadata.drop_all(bind=engine)
    engine.dispose()

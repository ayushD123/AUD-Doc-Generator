from __future__ import annotations

from io import BytesIO
from pathlib import Path
from shutil import copyfileobj
from typing import BinaryIO, Protocol

from fastapi import UploadFile

from app.core.config import Settings, get_settings


ALLOWED_FILE_EXTENSIONS = {
    ".docx",
    ".pptx",
    ".xlsx",
    ".xlsm",
    ".txt",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".mp3",
    ".m4a",
    ".mp4",
}


class StorageService(Protocol):
    def save_project_upload(
        self,
        project_id: str,
        file_id: str,
        file: UploadFile,
    ) -> tuple[str, str]:
        ...

    def read_bytes(self, storage_key: str) -> bytes:
        ...

    def write_bytes(self, storage_key: str, content: bytes) -> None:
        ...

    def write_file(self, storage_key: str, source_path: Path) -> None:
        ...

    def download_to_path(self, storage_key: str, destination_path: Path) -> None:
        ...

    def delete(self, storage_key: str) -> None:
        ...

    def exists(self, storage_key: str) -> bool:
        ...

    def local_path(self, storage_key: str) -> Path | None:
        ...


def sanitize_storage_filename(filename: str | None) -> str:
    safe_name = (filename or "uploaded_file").replace("\\", "/").split("/")[-1]
    safe_name = "".join(
        character if character.isalnum() or character in {" ", ".", "-", "_"} else "_"
        for character in safe_name
    ).strip()
    return safe_name or "uploaded_file"


def upload_storage_key(project_id: str, file_id: str, filename: str | None) -> str:
    safe_name = sanitize_storage_filename(filename)
    return f"projects/{project_id}/uploads/{file_id}_{safe_name}"


def get_file_type(filename: str | None) -> str:
    return Path(filename or "").suffix.lower().removeprefix(".")


class LocalStorageService:
    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root

    def resolve_key(self, storage_key: str) -> Path:
        candidate_path = self.storage_root / storage_key
        resolved_root = self.storage_root.resolve()
        resolved_candidate = candidate_path.resolve()

        if resolved_candidate != resolved_root and resolved_root not in resolved_candidate.parents:
            raise ValueError("Storage key resolves outside local storage root.")

        return resolved_candidate

    def save_project_upload(
        self,
        project_id: str,
        file_id: str,
        file: UploadFile,
    ) -> tuple[str, str]:
        storage_key = upload_storage_key(project_id, file_id, file.filename)
        destination = self.resolve_key(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        with destination.open("wb") as output:
            copyfileobj(file.file, output)

        return storage_key, get_file_type(file.filename)

    def read_bytes(self, storage_key: str) -> bytes:
        return self.resolve_key(storage_key).read_bytes()

    def write_bytes(self, storage_key: str, content: bytes) -> None:
        destination = self.resolve_key(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    def write_file(self, storage_key: str, source_path: Path) -> None:
        destination = self.resolve_key(storage_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source_path.read_bytes())

    def download_to_path(self, storage_key: str, destination_path: Path) -> None:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(self.read_bytes(storage_key))

    def delete(self, storage_key: str) -> None:
        path = self.resolve_key(storage_key)

        if path.is_file():
            path.unlink()

    def exists(self, storage_key: str) -> bool:
        return self.resolve_key(storage_key).is_file()

    def local_path(self, storage_key: str) -> Path | None:
        path = self.resolve_key(storage_key)
        return path if path.is_file() else None


class OCIObjectStorageService:
    def __init__(
        self,
        settings: Settings | None = None,
        client: object | None = None,
        upload_manager: object | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.bucket_name = self.require_setting(
            self.settings.OCI_BUCKET_NAME,
            "OCI_BUCKET_NAME",
        )
        self.namespace = self.require_setting(
            self.settings.OCI_NAMESPACE,
            "OCI_NAMESPACE",
        )
        self.client = client or self.build_client()
        self.upload_manager = upload_manager

    @staticmethod
    def require_setting(value: str | None, setting_name: str) -> str:
        if not value:
            raise ValueError(f"{setting_name} is required when STORAGE_BACKEND=oci.")

        return value

    def build_client(self) -> object:
        try:
            import oci
        except ImportError as error:
            raise RuntimeError(
                "OCI Python SDK is required when STORAGE_BACKEND=oci."
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

        return oci.object_storage.ObjectStorageClient(config)

    def get_upload_manager(self) -> object:
        if self.upload_manager is None:
            try:
                from oci.object_storage.transfer.upload_manager import UploadManager
            except ImportError as error:
                raise RuntimeError(
                    "OCI upload manager is required for multipart uploads."
                ) from error

            self.upload_manager = UploadManager(
                self.client,
                allow_multipart_uploads=True,
                allow_parallel_uploads=True,
                parallel_process_count=max(
                    1,
                    self.settings.OCI_MULTIPART_UPLOAD_PARALLEL_WORKERS,
                ),
            )

        return self.upload_manager

    @staticmethod
    def get_remaining_stream_length(content: BinaryIO) -> int | None:
        try:
            current_position = content.tell()
            content.seek(0, 2)
            end_position = content.tell()
            content.seek(current_position)
        except (AttributeError, OSError):
            return None

        return end_position - current_position

    def should_use_multipart_upload(self, content_length: int | None) -> bool:
        if content_length is None:
            return False

        return content_length >= self.settings.OCI_MULTIPART_UPLOAD_THRESHOLD_BYTES

    def upload_multipart_stream(
        self,
        storage_key: str,
        content: BinaryIO,
    ) -> None:
        upload_manager = self.get_upload_manager()
        upload_manager.upload_stream(
            self.namespace,
            self.bucket_name,
            storage_key,
            content,
            part_size=max(1, self.settings.OCI_MULTIPART_UPLOAD_PART_SIZE_BYTES),
        )

    def put_object(
        self,
        storage_key: str,
        content: bytes | BinaryIO,
        content_length: int | None = None,
    ) -> None:
        upload_kwargs = {}

        if content_length is not None:
            upload_kwargs["content_length"] = content_length
        elif isinstance(content, bytes):
            upload_kwargs["content_length"] = len(content)
        else:
            stream_length = self.get_remaining_stream_length(content)

            if stream_length is not None:
                upload_kwargs["content_length"] = stream_length

        self.client.put_object(
            self.namespace,
            self.bucket_name,
            storage_key,
            content,
            **upload_kwargs,
        )

    def save_project_upload(
        self,
        project_id: str,
        file_id: str,
        file: UploadFile,
    ) -> tuple[str, str]:
        storage_key = upload_storage_key(project_id, file_id, file.filename)
        content_length = self.get_remaining_stream_length(file.file)

        if self.should_use_multipart_upload(content_length):
            self.upload_multipart_stream(storage_key, file.file)
        else:
            self.put_object(storage_key, file.file, content_length=content_length)

        return storage_key, get_file_type(file.filename)

    def read_bytes(self, storage_key: str) -> bytes:
        response = self.client.get_object(
            self.namespace,
            self.bucket_name,
            storage_key,
        )
        return response.data.content

    def write_bytes(self, storage_key: str, content: bytes) -> None:
        if self.should_use_multipart_upload(len(content)):
            self.upload_multipart_stream(storage_key, BytesIO(content))
        else:
            self.put_object(storage_key, content, content_length=len(content))

    def write_file(self, storage_key: str, source_path: Path) -> None:
        with source_path.open("rb") as source:
            content_length = source_path.stat().st_size

            if self.should_use_multipart_upload(content_length):
                self.upload_multipart_stream(storage_key, source)
            else:
                self.put_object(storage_key, source, content_length=content_length)

    def download_to_path(self, storage_key: str, destination_path: Path) -> None:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(self.read_bytes(storage_key))

    def delete(self, storage_key: str) -> None:
        try:
            self.client.delete_object(
                self.namespace,
                self.bucket_name,
                storage_key,
            )
        except KeyError:
            return
        except Exception as error:
            if getattr(error, "status", None) == 404:
                return

            raise

    def exists(self, storage_key: str) -> bool:
        try:
            self.client.head_object(self.namespace, self.bucket_name, storage_key)
        except KeyError:
            return False
        except Exception as error:
            if getattr(error, "status", None) == 404:
                return False

            raise

        return True

    def local_path(self, storage_key: str) -> Path | None:
        return None


def get_local_storage_root() -> Path:
    settings = get_settings()
    configured_root = Path(settings.LOCAL_STORAGE_ROOT)

    if configured_root.is_absolute():
        return configured_root

    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / configured_root


def get_file_storage() -> StorageService:
    settings = get_settings()
    storage_backend = settings.STORAGE_BACKEND.strip().lower()

    if storage_backend == "local":
        return LocalStorageService(get_local_storage_root())

    if storage_backend == "oci":
        return OCIObjectStorageService(settings)

    raise ValueError("STORAGE_BACKEND must be either 'local' or 'oci'.")

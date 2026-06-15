from pathlib import Path
from shutil import copyfileobj
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings


ALLOWED_FILE_EXTENSIONS = {
    ".docx",
    ".pptx",
    ".xlsx",
    ".xlsm",
    ".txt",
    ".pdf",
    ".m4a",
    ".mp4",
}


class LocalFileStorageService:
    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root

    def save_project_upload(self, project_id: str, file: UploadFile) -> tuple[str, str]:
        original_filename = file.filename or "uploaded_file"
        extension = Path(original_filename).suffix.lower()
        stored_filename = f"{uuid4()}{extension}"
        storage_key = f"projects/{project_id}/uploads/{stored_filename}"
        destination = self.storage_root / storage_key

        destination.parent.mkdir(parents=True, exist_ok=True)

        with destination.open("wb") as output:
            copyfileobj(file.file, output)

        return storage_key, extension.removeprefix(".")


def get_local_storage_root() -> Path:
    settings = get_settings()
    configured_root = Path(settings.LOCAL_STORAGE_ROOT)

    if configured_root.is_absolute():
        return configured_root

    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / configured_root


def get_file_storage() -> LocalFileStorageService:
    return LocalFileStorageService(get_local_storage_root())

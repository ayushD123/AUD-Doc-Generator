from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from app.core.config import Settings
from app.services.file_storage import OCIObjectStorageService


class FakeOCIObjectStorageClient:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(
        self,
        namespace: str,
        bucket_name: str,
        object_name: str,
        content: bytes | BytesIO,
    ) -> None:
        if hasattr(content, "read"):
            self.objects[object_name] = content.read()
        else:
            self.objects[object_name] = content

    def get_object(
        self,
        namespace: str,
        bucket_name: str,
        object_name: str,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            data=SimpleNamespace(content=self.objects[object_name])
        )

    def head_object(
        self,
        namespace: str,
        bucket_name: str,
        object_name: str,
    ) -> None:
        if object_name not in self.objects:
            raise KeyError(object_name)


def test_oci_storage_uses_project_object_keys(tmp_path: Path) -> None:
    client = FakeOCIObjectStorageClient()
    storage = OCIObjectStorageService(
        settings=Settings(
            STORAGE_BACKEND="oci",
            OCI_BUCKET_NAME="aud-bucket",
            OCI_NAMESPACE="tenantnamespace",
            OCI_REGION="us-ashburn-1",
        ),
        client=client,
    )
    upload = SimpleNamespace(filename="Huber KT.pptx", file=BytesIO(b"ppt bytes"))

    storage_key, file_type = storage.save_project_upload(
        "project-123",
        "file-456",
        upload,
    )

    assert storage_key == "projects/project-123/uploads/file-456_Huber KT.pptx"
    assert file_type == "pptx"
    assert storage.read_bytes(storage_key) == b"ppt bytes"
    assert storage.exists(storage_key) is True

    output_path = tmp_path / "output.docx"
    output_path.write_bytes(b"docx bytes")
    output_key = "projects/project-123/outputs/output.docx"
    storage.write_file(output_key, output_path)

    assert storage.read_bytes(output_key) == b"docx bytes"

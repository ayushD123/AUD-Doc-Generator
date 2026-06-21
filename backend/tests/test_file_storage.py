from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from app.core.config import Settings
from app.services.file_storage import OCIObjectStorageService


class FakeOCIObjectStorageClient:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_lengths: dict[str, int | None] = {}

    def put_object(
        self,
        namespace: str,
        bucket_name: str,
        object_name: str,
        content: bytes | BytesIO,
        **kwargs: object,
    ) -> None:
        self.content_lengths[object_name] = kwargs.get("content_length")

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

    def delete_object(
        self,
        namespace: str,
        bucket_name: str,
        object_name: str,
    ) -> None:
        self.objects.pop(object_name, None)
        self.content_lengths.pop(object_name, None)


class FakeOCIUploadManager:
    def __init__(self, client: FakeOCIObjectStorageClient) -> None:
        self.client = client
        self.uploads: list[dict[str, object]] = []

    def upload_stream(
        self,
        namespace_name: str,
        bucket_name: str,
        object_name: str,
        stream_ref: BytesIO,
        **kwargs: object,
    ) -> None:
        self.uploads.append(
            {
                "namespace_name": namespace_name,
                "bucket_name": bucket_name,
                "object_name": object_name,
                "part_size": kwargs.get("part_size"),
            }
        )
        self.client.objects[object_name] = stream_ref.read()


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
    assert client.content_lengths[storage_key] == len(b"ppt bytes")
    assert storage.exists(storage_key) is True

    output_path = tmp_path / "output.docx"
    output_path.write_bytes(b"docx bytes")
    output_key = "projects/project-123/outputs/output.docx"
    storage.write_file(output_key, output_path)

    assert storage.read_bytes(output_key) == b"docx bytes"
    assert client.content_lengths[output_key] == len(b"docx bytes")

    storage.delete(storage_key)

    assert storage_key not in client.objects


def test_oci_storage_uses_parallel_multipart_for_large_uploads() -> None:
    client = FakeOCIObjectStorageClient()
    upload_manager = FakeOCIUploadManager(client)
    storage = OCIObjectStorageService(
        settings=Settings(
            STORAGE_BACKEND="oci",
            OCI_BUCKET_NAME="aud-bucket",
            OCI_NAMESPACE="tenantnamespace",
            OCI_REGION="us-ashburn-1",
            OCI_MULTIPART_UPLOAD_THRESHOLD_BYTES=10,
            OCI_MULTIPART_UPLOAD_PART_SIZE_BYTES=5,
            OCI_MULTIPART_UPLOAD_PARALLEL_WORKERS=4,
        ),
        client=client,
        upload_manager=upload_manager,
    )
    upload = SimpleNamespace(filename="large-session.m4a", file=BytesIO(b"x" * 12))

    storage_key, file_type = storage.save_project_upload(
        "project-123",
        "file-789",
        upload,
    )

    assert file_type == "m4a"
    assert storage.read_bytes(storage_key) == b"x" * 12
    assert storage_key not in client.content_lengths
    assert upload_manager.uploads == [
        {
            "namespace_name": "tenantnamespace",
            "bucket_name": "aud-bucket",
            "object_name": storage_key,
            "part_size": 5,
        }
    ]

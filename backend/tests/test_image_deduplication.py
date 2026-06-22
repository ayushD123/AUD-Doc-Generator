from __future__ import annotations

from pathlib import Path

from app.services.file_storage import LocalStorageService
from app.services.image_deduplication import ImageDeduplicationService


def build_service(tmp_path: Path) -> ImageDeduplicationService:
    return ImageDeduplicationService(LocalStorageService(tmp_path))


def write_image_bytes(tmp_path: Path, storage_path: str, content: bytes) -> None:
    path = tmp_path / storage_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_exact_duplicate_hash_removed(tmp_path: Path) -> None:
    write_image_bytes(tmp_path, "images/source.png", b"same-image")
    write_image_bytes(tmp_path, "images/copy.png", b"same-image")

    result = build_service(tmp_path).deduplicate(
        [
            {"image_id": "source", "storage_path": "images/source.png"},
            {"image_id": "copy", "storage_path": "images/copy.png"},
        ]
    )

    assert [candidate.image_id for candidate in result.retained_candidates] == [
        "source"
    ]
    assert result.duplicates_removed_count == 1
    assert result.removed_images[0].reason == "exact_content_hash"


def test_same_source_page_bounding_box_duplicate_removed(tmp_path: Path) -> None:
    write_image_bytes(tmp_path, "images/one.png", b"first-image")
    write_image_bytes(tmp_path, "images/two.png", b"second-image")

    result = build_service(tmp_path).deduplicate(
        [
            {
                "image_id": "page-crop-1",
                "storage_path": "images/one.png",
                "source_uploaded_file_id": "upload-1",
                "source_type": "du_image",
                "page_number": 4,
                "bounding_box": {"x": 10, "y": 20, "width": 30, "height": 40},
            },
            {
                "image_id": "page-crop-2",
                "storage_path": "images/two.png",
                "source_uploaded_file_id": "upload-1",
                "source_type": "rendered_page",
                "page_number": 4,
                "bounding_box": {"height": 40, "width": 30, "y": 20, "x": 10},
            },
        ]
    )

    assert len(result.retained_candidates) == 1
    assert result.removed_images[0].reason == "same_source_page_bounding_box"


def test_best_quality_image_retained(tmp_path: Path) -> None:
    write_image_bytes(tmp_path, "images/small.png", b"same-image")
    write_image_bytes(tmp_path, "images/large.png", b"same-image")

    result = build_service(tmp_path).deduplicate(
        [
            {
                "image_id": "small",
                "storage_path": "images/small.png",
                "source_type": "ppt_slide",
                "width_px": 200,
                "height_px": 100,
            },
            {
                "image_id": "large",
                "storage_path": "images/large.png",
                "source_type": "ppt_slide",
                "width_px": 800,
                "height_px": 400,
            },
        ]
    )

    assert [candidate.image_id for candidate in result.retained_candidates] == [
        "large"
    ]
    assert "replaced_by_better_quality" in result.removed_images[0].reason


def test_template_placeholder_images_excluded(tmp_path: Path) -> None:
    write_image_bytes(tmp_path, "images/placeholder.png", b"placeholder")

    result = build_service(tmp_path).deduplicate(
        [
            {
                "image_id": "placeholder",
                "storage_path": "images/placeholder.png",
                "caption": "<Insert diagram / screenshot here>",
            }
        ]
    )

    assert result.retained_candidates == []
    assert result.placeholder_removed_count == 1
    assert result.removed_images[0].reason == "template_placeholder"


def test_same_caption_different_content_not_removed_when_hash_differs(
    tmp_path: Path,
) -> None:
    write_image_bytes(tmp_path, "images/first.png", b"first-image")
    write_image_bytes(tmp_path, "images/second.png", b"second-image")

    result = build_service(tmp_path).deduplicate(
        [
            {
                "image_id": "first",
                "storage_path": "images/first.png",
                "source_uploaded_file_id": "upload-1",
                "caption": "System architecture",
                "width_px": 640,
                "height_px": 480,
                "perceptual_hash": "0000000000000000",
            },
            {
                "image_id": "second",
                "storage_path": "images/second.png",
                "source_uploaded_file_id": "upload-1",
                "caption": "System architecture",
                "width_px": 640,
                "height_px": 480,
                "perceptual_hash": "ffffffffffffffff",
            },
        ]
    )

    assert [candidate.image_id for candidate in result.retained_candidates] == [
        "first",
        "second",
    ]
    assert result.duplicates_removed_count == 0

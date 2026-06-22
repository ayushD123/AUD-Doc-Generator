from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from app.services.file_storage import StorageService

logger = logging.getLogger(__name__)

SOURCE_TYPE_PRIORITY = {
    "manual_upload": 50,
    "ppt_slide": 40,
    "docx_image": 38,
    "du_image": 34,
    "rendered_page": 10,
}
CONFIDENCE_SCORE = {
    "very_high": 1.0,
    "high": 0.85,
    "medium": 0.6,
    "low": 0.35,
}
PLACEHOLDER_MARKERS = {
    "<insert diagram / screenshot here>",
    "insert diagram / screenshot here",
    "insert screenshot here",
    "insert diagram here",
}
PERCEPTUAL_HASH_DISTANCE_THRESHOLD = 6


@dataclass(frozen=True)
class ImageCandidate:
    image_id: str
    storage_path: str
    source_uploaded_file_id: str | None = None
    source_role: str | None = None
    source_type: str = "manual_upload"
    section_id: str | None = None
    slide_number: int | None = None
    page_number: int | None = None
    bounding_box: Any = None
    caption: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    file_size_bytes: int | None = None
    checksum_hash: str | None = None
    perceptual_hash: str | None = None
    confidence_score: float | None = None
    original_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RemovedImage:
    image_id: str
    duplicate_of: str | None
    reason: str


@dataclass(frozen=True)
class ImageDeduplicationResult:
    retained_candidates: list[ImageCandidate]
    removed_images: list[RemovedImage]
    candidate_count: int
    placeholder_removed_count: int

    @property
    def duplicates_removed_count(self) -> int:
        return len(self.removed_images) - self.placeholder_removed_count

    def to_metadata(self) -> dict[str, Any]:
        return {
            "candidate_count": self.candidate_count,
            "retained_count": len(self.retained_candidates),
            "duplicates_removed_count": self.duplicates_removed_count,
            "placeholder_removed_count": self.placeholder_removed_count,
            "retained_image_ids": [
                candidate.image_id for candidate in self.retained_candidates
            ],
            "removed_images": [
                {
                    "image_id": removed.image_id,
                    "duplicate_of": removed.duplicate_of,
                    "reason": removed.reason,
                }
                for removed in self.removed_images
            ],
        }


class ImageDeduplicationService:
    def __init__(self, storage_service: StorageService) -> None:
        self.storage_service = storage_service

    def deduplicate(
        self,
        raw_candidates: list[dict[str, Any] | ImageCandidate],
    ) -> ImageDeduplicationResult:
        candidate_count = len(raw_candidates)
        retained: list[ImageCandidate] = []
        removed: list[RemovedImage] = []
        placeholder_removed_count = 0

        for index, raw_candidate in enumerate(raw_candidates, start=1):
            candidate = self.normalize_candidate(raw_candidate, index)
            if candidate is None:
                continue

            if self.is_placeholder(candidate):
                placeholder_removed_count += 1
                removed.append(
                    RemovedImage(
                        image_id=candidate.image_id,
                        duplicate_of=None,
                        reason="template_placeholder",
                    )
                )
                continue

            duplicate_index, reason = self.find_duplicate(candidate, retained)
            if duplicate_index is None:
                retained.append(candidate)
                continue

            existing = retained[duplicate_index]
            best = self.choose_best(existing, candidate)
            if best.image_id == candidate.image_id:
                retained[duplicate_index] = candidate
                removed.append(
                    RemovedImage(
                        image_id=existing.image_id,
                        duplicate_of=candidate.image_id,
                        reason=f"{reason}; replaced_by_better_quality",
                    )
                )
            else:
                removed.append(
                    RemovedImage(
                        image_id=candidate.image_id,
                        duplicate_of=existing.image_id,
                        reason=reason,
                    )
                )

        result = ImageDeduplicationResult(
            retained_candidates=retained,
            removed_images=removed,
            candidate_count=candidate_count,
            placeholder_removed_count=placeholder_removed_count,
        )
        logger.info(
            "Image deduplication candidates=%s retained=%s duplicates_removed=%s "
            "placeholder_removed=%s retained_ids=%s removed=%s",
            result.candidate_count,
            len(result.retained_candidates),
            result.duplicates_removed_count,
            result.placeholder_removed_count,
            [candidate.image_id for candidate in result.retained_candidates],
            [
                {
                    "image_id": item.image_id,
                    "duplicate_of": item.duplicate_of,
                    "reason": item.reason,
                }
                for item in result.removed_images
            ],
        )
        return result

    def normalize_candidate(
        self,
        raw_candidate: dict[str, Any] | ImageCandidate,
        index: int,
    ) -> ImageCandidate | None:
        if isinstance(raw_candidate, ImageCandidate):
            return self.enrich_candidate(raw_candidate)

        storage_path = raw_candidate.get("storage_path") or raw_candidate.get(
            "file_path"
        )
        if not isinstance(storage_path, str) or not storage_path:
            return None

        image_id = raw_candidate.get("image_id")
        if not isinstance(image_id, str) or not image_id:
            image_id = f"image-{index}"

        candidate = ImageCandidate(
            image_id=image_id,
            storage_path=storage_path,
            source_uploaded_file_id=string_or_none(
                raw_candidate.get("source_uploaded_file_id")
            ),
            source_role=string_or_none(raw_candidate.get("source_role")),
            source_type=string_or_default(raw_candidate.get("source_type"), "manual_upload"),
            section_id=string_or_none(raw_candidate.get("section_id")),
            slide_number=int_or_none(raw_candidate.get("slide_number")),
            page_number=int_or_none(raw_candidate.get("page_number")),
            bounding_box=raw_candidate.get("bounding_box"),
            caption=string_or_none(raw_candidate.get("caption")),
            width_px=int_or_none(raw_candidate.get("width_px")),
            height_px=int_or_none(raw_candidate.get("height_px")),
            file_size_bytes=int_or_none(raw_candidate.get("file_size_bytes")),
            checksum_hash=string_or_none(
                raw_candidate.get("checksum_hash") or raw_candidate.get("checksum")
            ),
            perceptual_hash=string_or_none(raw_candidate.get("perceptual_hash")),
            confidence_score=parse_confidence(raw_candidate.get("confidence_score")),
            original_payload=dict(raw_candidate),
        )
        return self.enrich_candidate(candidate)

    def enrich_candidate(self, candidate: ImageCandidate) -> ImageCandidate:
        content = self.read_candidate_bytes(candidate.storage_path)
        if content is None:
            return candidate

        width_px = candidate.width_px
        height_px = candidate.height_px
        perceptual_hash = candidate.perceptual_hash
        dimensions = get_image_dimensions(content)
        if dimensions is not None:
            width_px = width_px or dimensions[0]
            height_px = height_px or dimensions[1]

        if perceptual_hash is None:
            perceptual_hash = calculate_perceptual_hash(content)

        return ImageCandidate(
            image_id=candidate.image_id,
            storage_path=candidate.storage_path,
            source_uploaded_file_id=candidate.source_uploaded_file_id,
            source_role=candidate.source_role,
            source_type=candidate.source_type,
            section_id=candidate.section_id,
            slide_number=candidate.slide_number,
            page_number=candidate.page_number,
            bounding_box=candidate.bounding_box,
            caption=candidate.caption,
            width_px=width_px,
            height_px=height_px,
            file_size_bytes=candidate.file_size_bytes or len(content),
            checksum_hash=candidate.checksum_hash or hashlib.sha256(content).hexdigest(),
            perceptual_hash=perceptual_hash,
            confidence_score=candidate.confidence_score,
            original_payload=candidate.original_payload,
        )

    def read_candidate_bytes(self, storage_path: str) -> bytes | None:
        try:
            return self.storage_service.read_bytes(storage_path)
        except Exception:
            local_path = self.storage_service.local_path(storage_path)
            if local_path is None:
                return None
            try:
                return local_path.read_bytes()
            except OSError:
                return None

    def find_duplicate(
        self,
        candidate: ImageCandidate,
        retained: list[ImageCandidate],
    ) -> tuple[int | None, str]:
        for index, existing in enumerate(retained):
            reason = duplicate_reason(existing, candidate)
            if reason is not None:
                return index, reason

        return None, ""

    @staticmethod
    def choose_best(
        existing: ImageCandidate,
        candidate: ImageCandidate,
    ) -> ImageCandidate:
        return max((existing, candidate), key=quality_score)

    @staticmethod
    def is_placeholder(candidate: ImageCandidate) -> bool:
        values = [
            candidate.caption,
            candidate.original_payload.get("slide_title"),
            candidate.original_payload.get("title"),
            candidate.storage_path,
        ]
        normalized_values = [
            " ".join(str(value).lower().split())
            for value in values
            if value is not None
        ]
        return any(
            marker in normalized_value
            for marker in PLACEHOLDER_MARKERS
            for normalized_value in normalized_values
        )


def duplicate_reason(
    existing: ImageCandidate,
    candidate: ImageCandidate,
) -> str | None:
    if (
        existing.checksum_hash
        and candidate.checksum_hash
        and existing.checksum_hash == candidate.checksum_hash
    ):
        return "exact_content_hash"

    if same_source_reference(existing, candidate):
        return "same_source_page_bounding_box"

    if perceptual_hashes_close(existing.perceptual_hash, candidate.perceptual_hash):
        return "perceptual_hash_close_match"

    if (
        same_caption_dimensions_source(existing, candidate)
        and not conflicting_content_fingerprint(existing, candidate)
    ):
        return "same_caption_dimensions_source"

    return None


def same_source_reference(
    existing: ImageCandidate,
    candidate: ImageCandidate,
) -> bool:
    if not existing.source_uploaded_file_id or not candidate.source_uploaded_file_id:
        return False

    if existing.source_uploaded_file_id != candidate.source_uploaded_file_id:
        return False

    same_page = (
        existing.slide_number is not None
        and existing.slide_number == candidate.slide_number
    ) or (
        existing.page_number is not None
        and existing.page_number == candidate.page_number
    )
    if not same_page:
        return False

    existing_box = normalize_box(existing.bounding_box)
    candidate_box = normalize_box(candidate.bounding_box)
    if existing_box is None or candidate_box is None:
        return False

    return existing_box == candidate_box


def same_caption_dimensions_source(
    existing: ImageCandidate,
    candidate: ImageCandidate,
) -> bool:
    if normalize_text(existing.caption) != normalize_text(candidate.caption):
        return False

    if not normalize_text(existing.caption):
        return False

    if existing.source_uploaded_file_id != candidate.source_uploaded_file_id:
        return False

    return (
        existing.width_px is not None
        and existing.width_px == candidate.width_px
        and existing.height_px is not None
        and existing.height_px == candidate.height_px
    )


def conflicting_content_fingerprint(
    existing: ImageCandidate,
    candidate: ImageCandidate,
) -> bool:
    if (
        existing.checksum_hash
        and candidate.checksum_hash
        and existing.checksum_hash != candidate.checksum_hash
    ):
        if existing.perceptual_hash and candidate.perceptual_hash:
            return not perceptual_hashes_close(
                existing.perceptual_hash,
                candidate.perceptual_hash,
            )
        return True

    return False


def quality_score(candidate: ImageCandidate) -> tuple[float, int, int, int, int]:
    resolution = (candidate.width_px or 0) * (candidate.height_px or 0)
    source_priority = SOURCE_TYPE_PRIORITY.get(candidate.source_type, 20)
    relevance = candidate.confidence_score or 0.0
    file_size = candidate.file_size_bytes or 0
    manual_bonus = 1 if candidate.source_type == "manual_upload" else 0

    return (
        relevance,
        manual_bonus,
        source_priority,
        resolution,
        file_size,
    )


def perceptual_hashes_close(left: str | None, right: str | None) -> bool:
    if not left or not right or len(left) != len(right):
        return False

    try:
        distance = sum(
            bin(int(left_item, 16) ^ int(right_item, 16)).count("1")
            for left_item, right_item in zip(left, right, strict=True)
        )
    except ValueError:
        return False

    return distance <= PERCEPTUAL_HASH_DISTANCE_THRESHOLD


def calculate_perceptual_hash(content: bytes) -> str | None:
    try:
        import imagehash  # type: ignore
        from PIL import Image  # type: ignore

        with Image.open(BytesIO(content)) as image:
            return str(imagehash.phash(image))
    except Exception:
        pass

    try:
        from PIL import Image  # type: ignore

        with Image.open(BytesIO(content)) as image:
            image = image.convert("L").resize((8, 8))
            get_pixels = getattr(image, "get_flattened_data", image.getdata)
            pixels = list(get_pixels())
    except Exception:
        return None

    average = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= average else "0" for pixel in pixels)
    return f"{int(bits, 2):016x}"


def get_image_dimensions(content: bytes) -> tuple[int, int] | None:
    try:
        from PIL import Image  # type: ignore

        with Image.open(BytesIO(content)) as image:
            return image.size
    except Exception:
        return None


def normalize_box(value: Any) -> tuple[Any, ...] | None:
    if value is None:
        return None

    if isinstance(value, dict):
        return tuple((key, value[key]) for key in sorted(value))

    if isinstance(value, list):
        return tuple(value)

    if isinstance(value, tuple):
        return value

    return (value,)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""

    return " ".join(value.strip().split()).lower()


def string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def string_or_default(value: Any, default: str) -> str:
    return value if isinstance(value, str) and value else default


def int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    return None


def parse_confidence(value: Any) -> float | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        normalized = normalize_text(value).replace(" ", "_")
        return CONFIDENCE_SCORE.get(normalized)

    return None

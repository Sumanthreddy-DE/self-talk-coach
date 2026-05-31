"""Domain enums shared by the local-first learning core."""

from __future__ import annotations

from enum import StrEnum


class DateConfidence(StrEnum):
    """Confidence level for inferred session timestamps."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MediaStatus(StrEnum):
    """Lifecycle state for an imported media file."""

    IMPORTED = "imported"
    TRANSCRIBED = "transcribed"
    ANALYZED = "analyzed"
    FAILED = "failed"
    ARCHIVED = "archived"


class ImportOutcome(StrEnum):
    """Outcome category for one inbox file import attempt."""

    IMPORTED = "imported"
    DUPLICATE = "duplicate"
    FAILED = "failed"

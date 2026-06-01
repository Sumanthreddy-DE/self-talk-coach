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


class TranscriptStatus(StrEnum):
    """Storage status for one media transcription attempt."""

    COMPLETED = "completed"
    FAILED = "failed"


class TranscriptionOutcome(StrEnum):
    """Outcome category for one transcription run item."""

    TRANSCRIBED = "transcribed"
    SKIPPED = "skipped"
    FAILED = "failed"

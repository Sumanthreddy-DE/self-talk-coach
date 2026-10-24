"""Domain enums shared by the local-first learning core."""

from __future__ import annotations

from dataclasses import dataclass
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


class ConversationStatus(StrEnum):
    """Lifecycle state of one live conversation."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ABORTED = "aborted"


class TurnSpeaker(StrEnum):
    """Who produced a conversation turn."""

    LEARNER = "learner"
    PARTNER = "partner"


CONVERSATION_PRODUCER = "conversation"


class CandidateType(StrEnum):
    """Kind of learning candidate; values shared with the M3 first-language-analysis plan."""

    GRAMMAR_CORRECTION = "grammar_correction"
    PHRASE_UPGRADE = "phrase_upgrade"
    VOCABULARY = "vocabulary"


class ReportStatus(StrEnum):
    """Session-report state of one conversation."""

    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class NewCandidate:
    """A learning candidate found in one conversation turn."""

    turn_id: int
    candidate_type: CandidateType
    original_text: str
    suggested_text: str
    explanation: str

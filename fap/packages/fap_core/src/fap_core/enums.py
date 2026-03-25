"""Shared protocol enums for the Federated Agent Protocol."""

from enum import StrEnum


class ProtocolVersion(StrEnum):
    """Supported FAP protocol versions."""

    V0_1 = "0.1"


class MessageType(StrEnum):
    """Message types exchanged by FAP participants."""

    FAP_TASK_CREATE = "fap.task.create"
    FAP_TASK_ACCEPT = "fap.task.accept"
    FAP_TASK_REJECT = "fap.task.reject"
    FAP_TASK_COMPLETE = "fap.task.complete"
    FAP_AGGREGATE_SUBMIT = "fap.aggregate.submit"
    FAP_AGGREGATE_RESULT = "fap.aggregate.result"
    FAP_POLICY_ATTEST = "fap.policy.attest"
    FAP_EXCEPTION = "fap.exception"


class PrivacyClass(StrEnum):
    """Privacy classification for shared outputs."""

    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class SharingMode(StrEnum):
    """Policies for how participants may share derived results."""

    RAW = "raw"
    REDACTED = "redacted"
    SUMMARY_ONLY = "summary_only"
    VOTE_ONLY = "vote_only"


class TaskCompleteStatus(StrEnum):
    """Canonical task completion status values."""

    COMPLETED = "completed"


class AggregateContributionType(StrEnum):
    """Canonical participant aggregation contribution types."""

    SUMMARY = "summary"


class AggregationMode(StrEnum):
    """Canonical coordinator aggregation modes."""

    SUMMARY_MERGE = "summary_merge"


class PolicyTransformType(StrEnum):
    """Canonical policy transform types emitted on the wire."""

    RAW = "raw"
    REDACTED = "redacted"
    SUMMARY_ONLY = "summary_only"
    VOTE_ONLY = "vote_only"


class RunStatus(StrEnum):
    """Canonical coordinator run status values."""

    CREATED = "created"
    DECISIONS_RECORDED = "decisions_recorded"
    COMPLETED_RECORDED = "completed_recorded"
    AGGREGATED_RECORDED = "aggregated_recorded"


class ParticipantDecision(StrEnum):
    """Coordinator-facing response from a participant."""

    ACCEPT = "accept"
    REJECT = "reject"
    ACCEPT_WITH_CONSTRAINTS = "accept_with_constraints"

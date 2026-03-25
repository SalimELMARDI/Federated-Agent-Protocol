"""Tests for shared FAP enums."""

from fap_core.enums import (
    AggregateContributionType,
    AggregationMode,
    MessageType,
    ParticipantDecision,
    PolicyTransformType,
    PrivacyClass,
    ProtocolVersion,
    RunStatus,
    SharingMode,
    TaskCompleteStatus,
)


def test_protocol_version_values() -> None:
    """Protocol versions should match the published wire values."""
    assert {item.name: item.value for item in ProtocolVersion} == {"V0_1": "0.1"}


def test_message_type_values() -> None:
    """Message types should remain stable for the wire protocol."""
    assert {item.name: item.value for item in MessageType} == {
        "FAP_TASK_CREATE": "fap.task.create",
        "FAP_TASK_ACCEPT": "fap.task.accept",
        "FAP_TASK_REJECT": "fap.task.reject",
        "FAP_TASK_COMPLETE": "fap.task.complete",
        "FAP_AGGREGATE_SUBMIT": "fap.aggregate.submit",
        "FAP_AGGREGATE_RESULT": "fap.aggregate.result",
        "FAP_POLICY_ATTEST": "fap.policy.attest",
        "FAP_EXCEPTION": "fap.exception",
    }


def test_privacy_class_values() -> None:
    """Privacy classes should match the expected governance values."""
    assert {item.name: item.value for item in PrivacyClass} == {
        "PUBLIC": "public",
        "INTERNAL": "internal",
        "SENSITIVE": "sensitive",
        "RESTRICTED": "restricted",
    }


def test_sharing_mode_values() -> None:
    """Sharing modes should match the expected governance values."""
    assert {item.name: item.value for item in SharingMode} == {
        "RAW": "raw",
        "REDACTED": "redacted",
        "SUMMARY_ONLY": "summary_only",
        "VOTE_ONLY": "vote_only",
    }


def test_hardened_protocol_vocabulary_values() -> None:
    """Release-hardening enums should preserve the expected wire strings."""
    assert {item.name: item.value for item in TaskCompleteStatus} == {
        "COMPLETED": "completed",
    }
    assert {item.name: item.value for item in AggregateContributionType} == {
        "SUMMARY": "summary",
    }
    assert {item.name: item.value for item in AggregationMode} == {
        "SUMMARY_MERGE": "summary_merge",
    }
    assert {item.name: item.value for item in PolicyTransformType} == {
        "RAW": "raw",
        "REDACTED": "redacted",
        "SUMMARY_ONLY": "summary_only",
        "VOTE_ONLY": "vote_only",
    }
    assert {item.name: item.value for item in RunStatus} == {
        "CREATED": "created",
        "DECISIONS_RECORDED": "decisions_recorded",
        "COMPLETED_RECORDED": "completed_recorded",
        "AGGREGATED_RECORDED": "aggregated_recorded",
    }


def test_participant_decision_values() -> None:
    """Participant decisions should match the expected coordinator values."""
    assert {item.name: item.value for item in ParticipantDecision} == {
        "ACCEPT": "accept",
        "REJECT": "reject",
        "ACCEPT_WITH_CONSTRAINTS": "accept_with_constraints",
    }

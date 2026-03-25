"""Tests for the typed FAP message registry and parse API."""

from __future__ import annotations

from typing import Any, Callable

import pytest

from fap_core.clocks import utc_now
from fap_core.enums import (
    AggregateContributionType,
    AggregationMode,
    MessageType,
    PolicyTransformType,
    PrivacyClass,
    ProtocolVersion,
    SharingMode,
    TaskCompleteStatus,
)
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import (
    AggregateResultMessage,
    AggregateResultPayload,
    AggregateSubmitMessage,
    AggregateSubmitPayload,
    ExceptionMessage,
    ExceptionPayload,
    MESSAGE_MODELS_BY_KIND,
    MessageEnvelope,
    MessageParseError,
    PolicyAttestMessage,
    PolicyAttestPayload,
    UnsupportedProtocolVersionError,
    TaskAcceptMessage,
    TaskAcceptPayload,
    TaskCompleteMessage,
    TaskCompletePayload,
    TaskCreateMessage,
    TaskCreatePayload,
    TaskRejectMessage,
    TaskRejectPayload,
    UnknownMessageKindError,
    get_message_model,
    parse_message,
)


def build_envelope(message_type: MessageType, *, sender_id: str, recipient_id: str) -> MessageEnvelope:
    """Return a valid envelope for registry tests."""
    return MessageEnvelope(
        message_type=message_type,
        task_id=new_task_id(),
        run_id=new_run_id(),
        message_id=new_message_id(),
        sender_id=sender_id,
        recipient_id=recipient_id,
        domain_id="docs",
        trace_id=new_trace_id(),
        timestamp=utc_now(),
    )


def build_task_create_raw() -> dict[str, Any]:
    """Return a raw task create message for parser tests."""
    return TaskCreateMessage(
        envelope=build_envelope(
            MessageType.FAP_TASK_CREATE,
            sender_id="coordinator",
            recipient_id="participant_docs",
        ),
        payload=TaskCreatePayload(
            title="Summarize notes",
            description="Create a redacted summary for coordinator review.",
            requested_capabilities=["summarization", "redaction"],
            input_query="Summarize the incident notes.",
            constraints=["Do not expose names."],
        ),
    ).model_dump(mode="json")


def build_task_accept_raw() -> dict[str, Any]:
    """Return a raw task accept message for parser tests."""
    return TaskAcceptMessage(
        envelope=build_envelope(
            MessageType.FAP_TASK_ACCEPT,
            sender_id="participant_docs",
            recipient_id="coordinator",
        ),
        payload=TaskAcceptPayload(
            participant_id="participant_docs",
            accepted_capabilities=["summarization"],
            constraints=["summary only"],
            estimated_confidence=0.8,
            note="Redacted summary is supported.",
        ),
    ).model_dump(mode="json")


def build_task_reject_raw() -> dict[str, Any]:
    """Return a raw task reject message for parser tests."""
    return TaskRejectMessage(
        envelope=build_envelope(
            MessageType.FAP_TASK_REJECT,
            sender_id="participant_docs",
            recipient_id="coordinator",
        ),
        payload=TaskRejectPayload(
            participant_id="participant_docs",
            reason="Local source unavailable.",
            retryable=True,
            details="Retry after the connector is restored.",
        ),
    ).model_dump(mode="json")


def build_task_complete_raw() -> dict[str, Any]:
    """Return a raw task complete message for parser tests."""
    return TaskCompleteMessage(
        envelope=build_envelope(
            MessageType.FAP_TASK_COMPLETE,
            sender_id="participant_docs",
            recipient_id="coordinator",
        ),
        payload=TaskCompletePayload(
            participant_id="participant_docs",
            status=TaskCompleteStatus.COMPLETED,
            summary="Produced a redacted summary.",
            confidence=0.9,
            result_ref="results/docs/001",
        ),
    ).model_dump(mode="json")


def build_aggregate_submit_raw() -> dict[str, Any]:
    """Return a raw aggregate submit message for parser tests."""
    return AggregateSubmitMessage(
        envelope=build_envelope(
            MessageType.FAP_AGGREGATE_SUBMIT,
            sender_id="participant_docs",
            recipient_id="coordinator",
        ),
        payload=AggregateSubmitPayload(
            participant_id="participant_docs",
            contribution_type=AggregateContributionType.SUMMARY,
            summary="The incident appears low severity.",
            confidence=0.72,
            provenance_ref="prov/docs/001",
        ),
    ).model_dump(mode="json")


def build_aggregate_result_raw() -> dict[str, Any]:
    """Return a raw aggregate result message for parser tests."""
    return AggregateResultMessage(
        envelope=build_envelope(
            MessageType.FAP_AGGREGATE_RESULT,
            sender_id="coordinator",
            recipient_id="participant_docs",
        ),
        payload=AggregateResultPayload(
            aggregation_mode=AggregationMode.SUMMARY_MERGE,
            final_answer="Most participants agree on a low-severity incident.",
            participant_count=3,
            provenance_refs=["prov/docs/001", "prov/logs/001"],
            confidence=0.88,
        ),
    ).model_dump(mode="json")


def build_policy_attest_raw() -> dict[str, Any]:
    """Return a raw policy attest message for parser tests."""
    return PolicyAttestMessage(
        envelope=build_envelope(
            MessageType.FAP_POLICY_ATTEST,
            sender_id="participant_docs",
            recipient_id="coordinator",
        ),
        payload=PolicyAttestPayload(
            participant_id="participant_docs",
            policy_ref="policy/fap-v0.1",
            original_privacy_class=PrivacyClass.SENSITIVE,
            applied_sharing_mode=SharingMode.REDACTED,
            transform_type=PolicyTransformType.REDACTED,
            attestation_note="Names were removed before export.",
        ),
    ).model_dump(mode="json")


def build_exception_raw() -> dict[str, Any]:
    """Return a raw exception message for parser tests."""
    return ExceptionMessage(
        envelope=build_envelope(
            MessageType.FAP_EXCEPTION,
            sender_id="coordinator",
            recipient_id="participant_docs",
        ),
        payload=ExceptionPayload(
            code="participant.unavailable",
            message="The participant could not access its local source.",
            retryable=True,
            details="Retry after the connector is restored.",
        ),
    ).model_dump(mode="json")


@pytest.mark.parametrize(
    ("builder", "expected_type", "expected_kind"),
    [
        (build_task_create_raw, TaskCreateMessage, MessageType.FAP_TASK_CREATE),
        (build_task_accept_raw, TaskAcceptMessage, MessageType.FAP_TASK_ACCEPT),
        (build_task_reject_raw, TaskRejectMessage, MessageType.FAP_TASK_REJECT),
        (build_task_complete_raw, TaskCompleteMessage, MessageType.FAP_TASK_COMPLETE),
        (build_aggregate_submit_raw, AggregateSubmitMessage, MessageType.FAP_AGGREGATE_SUBMIT),
        (build_aggregate_result_raw, AggregateResultMessage, MessageType.FAP_AGGREGATE_RESULT),
        (build_policy_attest_raw, PolicyAttestMessage, MessageType.FAP_POLICY_ATTEST),
        (build_exception_raw, ExceptionMessage, MessageType.FAP_EXCEPTION),
    ],
)
def test_parse_message_supports_every_registered_kind(
    builder: Callable[[], dict[str, Any]],
    expected_type: type[object],
    expected_kind: MessageType,
) -> None:
    """Each supported message kind should parse into the correct concrete class."""
    parsed = parse_message(builder())

    assert isinstance(parsed, expected_type)
    assert parsed.envelope.message_type == expected_kind


def test_get_message_model_returns_registered_model() -> None:
    """Registry lookup should return the expected concrete message model."""
    assert get_message_model("fap.task.create") is TaskCreateMessage
    assert get_message_model("fap.exception") is ExceptionMessage
    assert get_message_model("fap.task.create", version=ProtocolVersion.V0_1) is TaskCreateMessage
    assert set(MESSAGE_MODELS_BY_KIND) == {
        MessageType.FAP_TASK_CREATE,
        MessageType.FAP_TASK_ACCEPT,
        MessageType.FAP_TASK_REJECT,
        MessageType.FAP_TASK_COMPLETE,
        MessageType.FAP_AGGREGATE_SUBMIT,
        MessageType.FAP_AGGREGATE_RESULT,
        MessageType.FAP_POLICY_ATTEST,
        MessageType.FAP_EXCEPTION,
    }


def test_get_message_model_rejects_unknown_kind() -> None:
    """Registry lookup should fail clearly for unknown kinds."""
    with pytest.raises(UnknownMessageKindError, match="Unsupported message kind"):
        get_message_model("fap.unknown")


def test_parse_message_rejects_unknown_kind() -> None:
    """The parser should surface a clear error for unknown message kinds."""
    data = build_task_create_raw()
    data["envelope"]["message_type"] = "fap.unknown"

    with pytest.raises(UnknownMessageKindError, match="Unsupported message kind"):
        parse_message(data)


def test_parse_message_rejects_unsupported_version() -> None:
    """The parser should fail clearly when a message declares an unsupported version."""
    data = build_task_create_raw()
    data["envelope"]["version"] = "0.2"

    with pytest.raises(
        UnsupportedProtocolVersionError,
        match=r"Unsupported protocol version for 'FAP': '0.2'",
    ):
        parse_message(data)


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"envelope": {}},
        {"envelope": "not-a-dict"},
        {"envelope": {"message_type": 123}},
    ],
)
def test_parse_message_rejects_malformed_envelope(data: dict[str, Any]) -> None:
    """The parser should fail clearly when it cannot extract the message kind."""
    with pytest.raises(MessageParseError, match="Malformed message envelope"):
        parse_message(data)


def test_parse_message_rejects_invalid_payload_for_known_kind() -> None:
    """The parser should wrap validation failures for supported kinds."""
    data = build_task_complete_raw()
    data["payload"]["summary"] = "   "

    with pytest.raises(MessageParseError, match="Failed to parse message kind 'fap.task.complete'"):
        parse_message(data)


def test_parse_message_smoke_examples_use_correct_concrete_classes() -> None:
    """A couple of raw messages should parse into the expected concrete classes."""
    task_create = parse_message(build_task_create_raw())
    exception_message = parse_message(build_exception_raw())

    assert isinstance(task_create, TaskCreateMessage)
    assert isinstance(exception_message, ExceptionMessage)

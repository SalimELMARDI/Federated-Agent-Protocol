"""Tests for the canonical FAP codec API."""

from __future__ import annotations

import json
from typing import Callable

import pytest

from fap_core import (
    MessageJsonDecodeError,
    MessageJsonShapeError,
    message_from_dict,
    message_from_json,
    message_to_dict,
    message_to_json,
)
from fap_core.clocks import utc_now
from fap_core.enums import AggregationMode, MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import (
    AggregateResultMessage,
    AggregateResultPayload,
    ExceptionMessage,
    ExceptionPayload,
    MessageEnvelope,
    MessageParseError,
    SourceRef,
    TaskCreateMessage,
    TaskCreatePayload,
    UnknownMessageKindError,
)


def build_envelope(message_type: MessageType, *, sender_id: str, recipient_id: str) -> MessageEnvelope:
    """Return a valid envelope for codec tests."""
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


def build_task_create_message() -> TaskCreateMessage:
    """Return a typed task create message for codec tests."""
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
    )


def build_exception_message() -> ExceptionMessage:
    """Return a typed exception message for codec tests."""
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
    )


def build_aggregate_result_message() -> AggregateResultMessage:
    """Return a typed aggregate result message for codec tests."""
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
            source_refs=[
                SourceRef(
                    participant_id="participant_docs",
                    source_id="doc-002",
                    source_title="Privacy Policy Memo",
                    source_path="examples/local_docs/data/doc-002__privacy-policy-memo.json",
                )
            ],
            confidence=0.88,
        ),
    )


@pytest.mark.parametrize(
    ("builder", "expected_type"),
    [
        (build_task_create_message, TaskCreateMessage),
        (build_exception_message, ExceptionMessage),
        (build_aggregate_result_message, AggregateResultMessage),
    ],
)
def test_message_round_trip_dict(
    builder: Callable[[], TaskCreateMessage | ExceptionMessage | AggregateResultMessage],
    expected_type: type[object],
) -> None:
    """Canonical dict serialization should round-trip through the typed parser."""
    raw = message_to_dict(builder())
    parsed = message_from_dict(raw)

    assert isinstance(parsed, expected_type)
    assert message_to_dict(parsed) == raw


@pytest.mark.parametrize(
    ("builder", "expected_type"),
    [
        (build_task_create_message, TaskCreateMessage),
        (build_exception_message, ExceptionMessage),
        (build_aggregate_result_message, AggregateResultMessage),
    ],
)
def test_message_round_trip_json(
    builder: Callable[[], TaskCreateMessage | ExceptionMessage | AggregateResultMessage],
    expected_type: type[object],
) -> None:
    """Canonical JSON serialization should round-trip through the typed parser."""
    encoded = message_to_json(builder())
    parsed = message_from_json(encoded)

    assert "\n" not in encoded
    assert isinstance(parsed, expected_type)
    assert message_to_json(parsed) == encoded


def test_message_from_json_rejects_invalid_json() -> None:
    """Invalid JSON text should raise a codec-specific decode error."""
    with pytest.raises(MessageJsonDecodeError, match="Invalid JSON message payload"):
        message_from_json("{not-json}")


@pytest.mark.parametrize("data", ['[]', '"not-an-object"', "123", "true"])
def test_message_from_json_rejects_non_object_json(data: str) -> None:
    """Top-level JSON must decode into an object for FAP messages."""
    with pytest.raises(MessageJsonShapeError, match="Top-level JSON value must be an object"):
        message_from_json(data)


def test_message_from_json_preserves_unknown_kind_error() -> None:
    """Unknown message kinds should still surface the registry error."""
    raw = message_to_dict(build_task_create_message())
    envelope = raw["envelope"]
    assert isinstance(envelope, dict)
    envelope["message_type"] = "fap.unknown"

    with pytest.raises(UnknownMessageKindError, match="Unsupported message kind"):
        message_from_json(json.dumps(raw))


def test_message_from_json_preserves_known_kind_parse_error() -> None:
    """Known kinds with invalid payloads should still raise parse errors."""
    raw = message_to_dict(build_task_create_message())
    payload = raw["payload"]
    assert isinstance(payload, dict)
    payload["title"] = "   "

    with pytest.raises(MessageParseError, match="Failed to parse message kind 'fap.task.create'"):
        message_from_json(json.dumps(raw))


def test_message_from_json_rejects_unsupported_protocol_version() -> None:
    """Unsupported envelope versions should fail clearly during parse."""
    raw = message_to_dict(build_task_create_message())
    envelope = raw["envelope"]
    assert isinstance(envelope, dict)
    envelope["version"] = "0.2"

    with pytest.raises(MessageParseError, match="Unsupported protocol version for 'FAP': '0.2'"):
        message_from_json(json.dumps(raw))


def test_message_to_dict_serializes_json_safe_smoke_examples() -> None:
    """Canonical dict output should already be JSON-safe for representative messages."""
    task_create_raw = message_to_dict(build_task_create_message())
    exception_raw = message_to_dict(build_exception_message())
    aggregate_raw = message_to_dict(build_aggregate_result_message())

    for raw in (task_create_raw, exception_raw, aggregate_raw):
        envelope = raw["envelope"]
        assert isinstance(envelope, dict)
        assert isinstance(envelope["timestamp"], str)
        assert json.loads(json.dumps(raw)) == raw

    aggregate_payload = aggregate_raw["payload"]
    assert isinstance(aggregate_payload, dict)
    assert aggregate_payload["source_refs"] == [
        {
            "participant_id": "participant_docs",
            "source_id": "doc-002",
            "source_title": "Privacy Policy Memo",
            "source_path": "examples/local_docs/data/doc-002__privacy-policy-memo.json",
        }
    ]


def test_message_from_json_smoke_examples_parse_to_expected_types() -> None:
    """Representative JSON messages should parse back into concrete classes."""
    task_create = message_from_json(message_to_json(build_task_create_message()))
    exception_message = message_from_json(message_to_json(build_exception_message()))
    aggregate_result = message_from_json(message_to_json(build_aggregate_result_message()))

    assert isinstance(task_create, TaskCreateMessage)
    assert isinstance(exception_message, ExceptionMessage)
    assert isinstance(aggregate_result, AggregateResultMessage)

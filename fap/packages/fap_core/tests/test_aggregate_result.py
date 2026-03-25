"""Tests for the aggregate result message model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fap_core.clocks import utc_now
from fap_core.enums import AggregationMode, MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import AggregateResultMessage, AggregateResultPayload, MessageEnvelope, SourceRef


def build_envelope(message_type: MessageType) -> MessageEnvelope:
    """Return a valid envelope for aggregate message tests."""
    return MessageEnvelope(
        message_type=message_type,
        task_id=new_task_id(),
        run_id=new_run_id(),
        message_id=new_message_id(),
        sender_id="coordinator",
        recipient_id="participant_docs",
        domain_id="docs",
        trace_id=new_trace_id(),
        timestamp=utc_now(),
    )


def test_aggregate_result_message_accepts_valid_data() -> None:
    """A valid aggregate result message should parse cleanly."""
    message = AggregateResultMessage(
        envelope=build_envelope(MessageType.FAP_AGGREGATE_RESULT),
        payload=AggregateResultPayload(
            aggregation_mode=AggregationMode.SUMMARY_MERGE,
            final_answer="Most participants agree on a low-severity incident.",
            participant_count=3,
            provenance_refs=["prov/docs/001", "prov/logs/001"],
            confidence=0.9,
        ),
    )

    assert message.envelope.message_type == MessageType.FAP_AGGREGATE_RESULT
    assert message.payload.aggregation_mode == AggregationMode.SUMMARY_MERGE
    assert message.payload.participant_count == 3
    assert message.payload.source_refs == []


def test_aggregate_result_message_accepts_source_refs() -> None:
    """Aggregate results should support optional merged source refs."""
    message = AggregateResultMessage(
        envelope=build_envelope(MessageType.FAP_AGGREGATE_RESULT),
        payload=AggregateResultPayload(
            aggregation_mode=AggregationMode.SUMMARY_MERGE,
            final_answer="Most participants agree on a low-severity incident.",
            participant_count=1,
            source_refs=[
                SourceRef(
                    participant_id="participant_docs",
                    source_id="doc-002",
                    source_title="Privacy Policy Memo",
                    source_path="examples/local_docs/data/doc-002__privacy-policy-memo.json",
                )
            ],
        ),
    )

    assert message.model_dump(mode="json")["payload"]["source_refs"] == [
        {
            "participant_id": "participant_docs",
            "source_id": "doc-002",
            "source_title": "Privacy Policy Memo",
            "source_path": "examples/local_docs/data/doc-002__privacy-policy-memo.json",
        }
    ]


@pytest.mark.parametrize("field_name", ["aggregation_mode", "final_answer"])
def test_aggregate_result_payload_rejects_blank_required_strings(field_name: str) -> None:
    """Required aggregate result strings should reject blank values."""
    payload: dict[str, object] = {
        "aggregation_mode": "summary_merge",
        "final_answer": "Final answer",
        "participant_count": 2,
    }
    payload[field_name] = "   "

    with pytest.raises(ValidationError):
        AggregateResultPayload.model_validate(payload)


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_aggregate_result_payload_rejects_invalid_confidence(value: float) -> None:
    """Confidence values must stay within the inclusive 0..1 range."""
    with pytest.raises(ValidationError):
        AggregateResultPayload(
            aggregation_mode=AggregationMode.SUMMARY_MERGE,
            final_answer="Final answer",
            participant_count=2,
            confidence=value,
        )


def test_aggregate_result_payload_rejects_negative_participant_count() -> None:
    """Participant counts must not be negative."""
    with pytest.raises(ValidationError):
        AggregateResultPayload(
            aggregation_mode=AggregationMode.SUMMARY_MERGE,
            final_answer="Final answer",
            participant_count=-1,
        )


def test_aggregate_result_message_rejects_wrong_envelope_type() -> None:
    """Aggregate result messages should enforce the matching envelope type."""
    with pytest.raises(ValidationError):
        AggregateResultMessage(
            envelope=build_envelope(MessageType.FAP_AGGREGATE_SUBMIT),
            payload=AggregateResultPayload(
                aggregation_mode=AggregationMode.SUMMARY_MERGE,
                final_answer="Final answer",
                participant_count=2,
            ),
        )

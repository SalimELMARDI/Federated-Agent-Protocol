"""Tests for the aggregate submit message model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fap_core.clocks import utc_now
from fap_core.enums import AggregateContributionType, MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import (
    AggregateSubmitMessage,
    AggregateSubmitPayload,
    MessageEnvelope,
    SourceRef,
)


def build_envelope(message_type: MessageType) -> MessageEnvelope:
    """Return a valid envelope for aggregate message tests."""
    return MessageEnvelope(
        message_type=message_type,
        task_id=new_task_id(),
        run_id=new_run_id(),
        message_id=new_message_id(),
        sender_id="participant_docs",
        recipient_id="coordinator",
        domain_id="docs",
        trace_id=new_trace_id(),
        timestamp=utc_now(),
    )


def test_aggregate_submit_message_accepts_valid_data() -> None:
    """A valid aggregate submit message should parse cleanly."""
    message = AggregateSubmitMessage(
        envelope=build_envelope(MessageType.FAP_AGGREGATE_SUBMIT),
        payload=AggregateSubmitPayload(
            participant_id="participant_docs",
            contribution_type=AggregateContributionType.SUMMARY,
            summary="The incident was low severity.",
            confidence=0.72,
            provenance_ref="prov/docs/001",
        ),
    )

    assert message.envelope.message_type == MessageType.FAP_AGGREGATE_SUBMIT
    assert message.payload.contribution_type == AggregateContributionType.SUMMARY
    assert message.payload.summary == "The incident was low severity."
    assert message.payload.source_refs == []


def test_aggregate_submit_message_accepts_source_refs() -> None:
    """Aggregate submissions should support optional structured source refs."""
    message = AggregateSubmitMessage(
        envelope=build_envelope(MessageType.FAP_AGGREGATE_SUBMIT),
        payload=AggregateSubmitPayload(
            participant_id="participant_docs",
            contribution_type=AggregateContributionType.SUMMARY,
            summary="The incident was low severity.",
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


@pytest.mark.parametrize("field_name", ["participant_id", "contribution_type"])
def test_aggregate_submit_payload_rejects_blank_required_strings(field_name: str) -> None:
    """Required aggregate submit strings should reject blank values."""
    payload: dict[str, object] = {
        "participant_id": "participant_docs",
        "contribution_type": "summary",
        "summary": "The incident was low severity.",
    }
    payload[field_name] = "   "

    with pytest.raises(ValidationError):
        AggregateSubmitPayload.model_validate(payload)


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_aggregate_submit_payload_rejects_invalid_confidence(value: float) -> None:
    """Confidence values must stay within the inclusive 0..1 range."""
    with pytest.raises(ValidationError):
        AggregateSubmitPayload(
            participant_id="participant_docs",
            contribution_type=AggregateContributionType.SUMMARY,
            summary="The incident was low severity.",
            confidence=value,
        )


def test_aggregate_submit_payload_rejects_missing_summary_and_vote() -> None:
    """Aggregate submissions must include either a summary or a vote."""
    with pytest.raises(ValidationError):
        AggregateSubmitPayload(
            participant_id="participant_docs",
            contribution_type=AggregateContributionType.SUMMARY,
        )


def test_aggregate_submit_message_rejects_wrong_envelope_type() -> None:
    """Aggregate submit messages should enforce the matching envelope type."""
    with pytest.raises(ValidationError):
        AggregateSubmitMessage(
            envelope=build_envelope(MessageType.FAP_AGGREGATE_RESULT),
            payload=AggregateSubmitPayload(
                participant_id="participant_docs",
                contribution_type=AggregateContributionType.SUMMARY,
                summary="The incident was low severity.",
            ),
        )

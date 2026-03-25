"""Tests for the task acceptance message model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fap_core.clocks import utc_now
from fap_core.enums import MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import MessageEnvelope, TaskAcceptMessage, TaskAcceptPayload


def build_envelope(message_type: MessageType) -> MessageEnvelope:
    """Return a valid envelope for task message tests."""
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


def test_task_accept_message_accepts_valid_data() -> None:
    """A valid task accept message should parse cleanly."""
    message = TaskAcceptMessage(
        envelope=build_envelope(MessageType.FAP_TASK_ACCEPT),
        payload=TaskAcceptPayload(
            participant_id="participant_docs",
            accepted_capabilities=["summarization"],
            constraints=["summary only"],
            estimated_confidence=0.8,
            note="Can deliver a redacted summary.",
        ),
    )

    assert message.envelope.message_type == MessageType.FAP_TASK_ACCEPT
    assert message.payload.estimated_confidence == pytest.approx(0.8)


def test_task_accept_message_rejects_wrong_envelope_type() -> None:
    """Task accept messages should enforce the matching envelope type."""
    with pytest.raises(ValidationError):
        TaskAcceptMessage(
            envelope=build_envelope(MessageType.FAP_TASK_REJECT),
            payload=TaskAcceptPayload(participant_id="participant_docs"),
        )


def test_task_accept_payload_rejects_blank_participant_id() -> None:
    """Participant IDs should reject blank values."""
    with pytest.raises(ValidationError):
        TaskAcceptPayload(participant_id="   ")


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_task_accept_payload_rejects_invalid_confidence(value: float) -> None:
    """Confidence values must stay within the inclusive 0..1 range."""
    with pytest.raises(ValidationError):
        TaskAcceptPayload(participant_id="participant_docs", estimated_confidence=value)


def test_task_accept_payload_rejects_blank_note() -> None:
    """Optional notes should reject blank strings."""
    with pytest.raises(ValidationError):
        TaskAcceptPayload(participant_id="participant_docs", note="   ")

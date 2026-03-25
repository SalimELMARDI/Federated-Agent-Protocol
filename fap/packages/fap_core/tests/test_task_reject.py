"""Tests for the task rejection message model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fap_core.clocks import utc_now
from fap_core.enums import MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import MessageEnvelope, TaskRejectMessage, TaskRejectPayload


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


def test_task_reject_message_accepts_valid_data() -> None:
    """A valid task reject message should parse cleanly."""
    message = TaskRejectMessage(
        envelope=build_envelope(MessageType.FAP_TASK_REJECT),
        payload=TaskRejectPayload(
            participant_id="participant_docs",
            reason="Required capability unavailable.",
            retryable=True,
            details="Retry after the document parser is available.",
        ),
    )

    assert message.envelope.message_type == MessageType.FAP_TASK_REJECT
    assert message.payload.retryable is True


def test_task_reject_message_rejects_wrong_envelope_type() -> None:
    """Task reject messages should enforce the matching envelope type."""
    with pytest.raises(ValidationError):
        TaskRejectMessage(
            envelope=build_envelope(MessageType.FAP_TASK_ACCEPT),
            payload=TaskRejectPayload(
                participant_id="participant_docs",
                reason="Required capability unavailable.",
            ),
        )


@pytest.mark.parametrize("field_name", ["participant_id", "reason"])
def test_task_reject_payload_rejects_blank_required_strings(field_name: str) -> None:
    """Participant ID and reason should reject blank values."""
    payload = {
        "participant_id": "participant_docs",
        "reason": "Capability unavailable.",
    }
    payload[field_name] = "   "

    with pytest.raises(ValidationError):
        TaskRejectPayload.model_validate(payload)


def test_task_reject_payload_rejects_blank_details() -> None:
    """Optional details should reject blank strings."""
    with pytest.raises(ValidationError):
        TaskRejectPayload(
            participant_id="participant_docs",
            reason="Capability unavailable.",
            details="   ",
        )

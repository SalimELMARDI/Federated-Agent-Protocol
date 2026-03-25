"""Tests for the exception message model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fap_core.clocks import utc_now
from fap_core.enums import MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import ExceptionMessage, ExceptionPayload, MessageEnvelope


def build_envelope(message_type: MessageType) -> MessageEnvelope:
    """Return a valid envelope for exception message tests."""
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


def test_exception_message_accepts_valid_data() -> None:
    """A valid exception message should parse cleanly."""
    message = ExceptionMessage(
        envelope=build_envelope(MessageType.FAP_EXCEPTION),
        payload=ExceptionPayload(
            code="participant.unavailable",
            message="The participant could not access its local data source.",
            retryable=True,
            details="Retry after the source connector is restored.",
        ),
    )

    assert message.envelope.message_type == MessageType.FAP_EXCEPTION
    assert message.payload.retryable is True


@pytest.mark.parametrize("field_name", ["code", "message"])
def test_exception_payload_rejects_blank_required_strings(field_name: str) -> None:
    """Required exception strings should reject blank values."""
    payload: dict[str, object] = {
        "code": "participant.unavailable",
        "message": "The participant could not access its local data source.",
    }
    payload[field_name] = "   "

    with pytest.raises(ValidationError):
        ExceptionPayload.model_validate(payload)


def test_exception_payload_rejects_blank_details() -> None:
    """Optional details should reject blank strings."""
    with pytest.raises(ValidationError):
        ExceptionPayload(
            code="participant.unavailable",
            message="The participant could not access its local data source.",
            details="   ",
        )


def test_exception_message_rejects_wrong_envelope_type() -> None:
    """Exception messages should enforce the matching envelope type."""
    with pytest.raises(ValidationError):
        ExceptionMessage(
            envelope=build_envelope(MessageType.FAP_TASK_REJECT),
            payload=ExceptionPayload(
                code="participant.unavailable",
                message="The participant could not access its local data source.",
            ),
        )

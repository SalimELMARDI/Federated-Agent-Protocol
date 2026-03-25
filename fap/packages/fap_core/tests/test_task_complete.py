"""Tests for the task completion message model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fap_core.clocks import utc_now
from fap_core.enums import MessageType, TaskCompleteStatus
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import MessageEnvelope, SourceRef, TaskCompleteMessage, TaskCompletePayload


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


def test_task_complete_message_accepts_valid_data() -> None:
    """A valid task complete message should parse cleanly."""
    message = TaskCompleteMessage(
        envelope=build_envelope(MessageType.FAP_TASK_COMPLETE),
        payload=TaskCompletePayload(
            participant_id="participant_docs",
            status=TaskCompleteStatus.COMPLETED,
            summary="Produced a redacted summary.",
            confidence=0.85,
            result_ref="results/docs/001",
        ),
    )

    assert message.envelope.message_type == MessageType.FAP_TASK_COMPLETE
    assert message.payload.status == TaskCompleteStatus.COMPLETED
    assert message.payload.confidence == pytest.approx(0.85)
    assert message.payload.source_refs == []


def test_task_complete_message_accepts_source_refs() -> None:
    """Task complete payloads should support optional structured source refs."""
    message = TaskCompleteMessage(
        envelope=build_envelope(MessageType.FAP_TASK_COMPLETE),
        payload=TaskCompletePayload(
            participant_id="participant_docs",
            status=TaskCompleteStatus.COMPLETED,
            summary="Produced a redacted summary.",
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


@pytest.mark.parametrize("field_name", ["participant_id", "status", "summary"])
def test_task_complete_payload_rejects_blank_required_strings(field_name: str) -> None:
    """Required task complete strings should reject blank values."""
    payload: dict[str, object] = {
        "participant_id": "participant_docs",
        "status": "completed",
        "summary": "Produced a redacted summary.",
    }
    payload[field_name] = "   "

    with pytest.raises(ValidationError):
        TaskCompletePayload.model_validate(payload)


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_task_complete_payload_rejects_invalid_confidence(value: float) -> None:
    """Confidence values must stay within the inclusive 0..1 range."""
    with pytest.raises(ValidationError):
        TaskCompletePayload(
            participant_id="participant_docs",
            status=TaskCompleteStatus.COMPLETED,
            summary="Produced a redacted summary.",
            confidence=value,
        )


def test_task_complete_message_rejects_wrong_envelope_type() -> None:
    """Task complete messages should enforce the matching envelope type."""
    with pytest.raises(ValidationError):
        TaskCompleteMessage(
            envelope=build_envelope(MessageType.FAP_TASK_ACCEPT),
            payload=TaskCompletePayload(
                participant_id="participant_docs",
                status=TaskCompleteStatus.COMPLETED,
                summary="Produced a redacted summary.",
            ),
        )

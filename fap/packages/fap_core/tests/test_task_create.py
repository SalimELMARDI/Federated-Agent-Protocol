"""Tests for the task creation message model."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from fap_core.clocks import utc_now
from fap_core.enums import MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import MessageEnvelope, TaskCreateMessage, TaskCreatePayload


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


def test_task_create_message_accepts_valid_data() -> None:
    """A valid task create message should parse cleanly."""
    message = TaskCreateMessage(
        envelope=build_envelope(MessageType.FAP_TASK_CREATE),
        payload=TaskCreatePayload(
            title="Summarize incident notes",
            description="Produce a redacted summary of the provided notes.",
            requested_capabilities=["summarization", "redaction"],
            input_query="Summarize the incident timeline.",
            constraints=["Do not disclose names."],
            deadline=utc_now(),
            budget="low",
        ),
    )

    assert message.envelope.message_type == MessageType.FAP_TASK_CREATE
    assert message.payload.requested_capabilities == ["summarization", "redaction"]


@pytest.mark.parametrize("field_name", ["title", "description", "input_query"])
def test_task_create_payload_rejects_blank_required_strings(field_name: str) -> None:
    """Required task create strings should reject blank values."""
    payload = {
        "title": "Task title",
        "description": "Task description",
        "requested_capabilities": ["summarization"],
        "input_query": "Input query",
        "constraints": ["redact pii"],
    }
    payload[field_name] = "   "

    with pytest.raises(ValidationError):
        TaskCreatePayload.model_validate(payload)


def test_task_create_payload_rejects_blank_list_entries() -> None:
    """Capability and constraint entries should reject blank values."""
    with pytest.raises(ValidationError):
        TaskCreatePayload(
            title="Task title",
            description="Task description",
            requested_capabilities=["summarization", "   "],
            input_query="Input query",
            constraints=[],
        )


def test_task_create_message_rejects_wrong_envelope_type() -> None:
    """Task create messages should enforce the matching envelope type."""
    with pytest.raises(ValidationError):
        TaskCreateMessage(
            envelope=build_envelope(MessageType.FAP_TASK_ACCEPT),
            payload=TaskCreatePayload(
                title="Task title",
                description="Task description",
                input_query="Input query",
            ),
        )


def test_task_create_payload_rejects_naive_deadline() -> None:
    """Task create deadlines must be timezone-aware."""
    with pytest.raises(ValidationError):
        TaskCreatePayload(
            title="Task title",
            description="Task description",
            input_query="Input query",
            deadline=datetime(2026, 3, 21, 14, 0, 0),
        )

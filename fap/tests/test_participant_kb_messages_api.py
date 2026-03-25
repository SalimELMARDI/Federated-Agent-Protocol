"""Tests for the participant_kb protocol ingress endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from fap_core import message_to_dict
from fap_core.clocks import utc_now
from fap_core.enums import MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import (
    ExceptionMessage,
    ExceptionPayload,
    MessageEnvelope,
    TaskCreateMessage,
    TaskCreatePayload,
)
from participant_kb.main import app

client = TestClient(app)


def build_envelope(message_type: MessageType, *, sender_id: str, recipient_id: str) -> MessageEnvelope:
    """Return a valid envelope for participant_kb API tests."""
    return MessageEnvelope(
        message_type=message_type,
        task_id=new_task_id(),
        run_id=new_run_id(),
        message_id=new_message_id(),
        sender_id=sender_id,
        recipient_id=recipient_id,
        domain_id="kb",
        trace_id=new_trace_id(),
        timestamp=utc_now(),
    )


def build_task_create_message() -> TaskCreateMessage:
    """Return a valid task create message."""
    return TaskCreateMessage(
        envelope=build_envelope(
            MessageType.FAP_TASK_CREATE,
            sender_id="coordinator",
            recipient_id="participant_kb",
        ),
        payload=TaskCreatePayload(
            title="Query local KB",
            description="Retrieve deterministic KB facts for coordinator review.",
            requested_capabilities=["kb.lookup", "kb.facts"],
            input_query="privacy",
            constraints=["Do not expose names."],
        ),
    )


def build_exception_message() -> ExceptionMessage:
    """Return a valid exception message."""
    return ExceptionMessage(
        envelope=build_envelope(
            MessageType.FAP_EXCEPTION,
            sender_id="coordinator",
            recipient_id="participant_kb",
        ),
        payload=ExceptionPayload(
            code="participant.unavailable",
            message="The participant could not access its local source.",
            retryable=True,
            details="Retry after the connector is restored.",
        ),
    )


def test_messages_endpoint_accepts_task_create_message() -> None:
    """Valid task create messages should be accepted."""
    message = build_task_create_message()

    response = client.post("/messages", json=message_to_dict(message))

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "message_type": "fap.task.create",
        "message_id": message.envelope.message_id,
        "task_id": message.envelope.task_id,
        "run_id": message.envelope.run_id,
        "service": "participant_kb",
    }


def test_messages_endpoint_accepts_exception_message() -> None:
    """Valid exception messages should be accepted."""
    message = build_exception_message()

    response = client.post("/messages", json=message_to_dict(message))

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "message_type": "fap.exception",
        "message_id": message.envelope.message_id,
        "task_id": message.envelope.task_id,
        "run_id": message.envelope.run_id,
        "service": "participant_kb",
    }


def test_messages_endpoint_rejects_unknown_message_kind() -> None:
    """Unknown message kinds should return an explicit 400 response."""
    raw_message = message_to_dict(build_task_create_message())
    envelope = raw_message["envelope"]
    assert isinstance(envelope, dict)
    envelope["message_type"] = "fap.unknown"

    response = client.post("/messages", json=raw_message)

    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "code": "unsupported_message_kind",
            "message": "Unsupported message kind: 'fap.unknown'",
        }
    }


def test_messages_endpoint_rejects_malformed_known_kind_payload() -> None:
    """Known message kinds with invalid payloads should return 422."""
    raw_message = message_to_dict(build_task_create_message())
    payload = raw_message["payload"]
    assert isinstance(payload, dict)
    payload["title"] = "   "

    response = client.post("/messages", json=raw_message)

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "invalid_message",
            "message": "Failed to parse message kind 'fap.task.create'.",
        }
    }


def test_health_endpoint_still_works() -> None:
    """Participant_kb health route should still be available."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "participant_kb"}

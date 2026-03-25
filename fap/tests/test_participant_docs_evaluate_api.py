"""Tests for the participant docs evaluation endpoint."""

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
from participant_docs.main import app

client = TestClient(app)


def build_envelope(message_type: MessageType, *, sender_id: str, recipient_id: str) -> MessageEnvelope:
    """Return a valid envelope for participant docs evaluate API tests."""
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


def build_task_create_message(requested_capabilities: list[str]) -> TaskCreateMessage:
    """Return a valid task-create message for evaluate endpoint tests."""
    return TaskCreateMessage(
        envelope=build_envelope(
            MessageType.FAP_TASK_CREATE,
            sender_id="coordinator",
            recipient_id="participant_docs",
        ),
        payload=TaskCreatePayload(
            title="Summarize notes",
            description="Create a redacted summary for coordinator review.",
            requested_capabilities=requested_capabilities,
            input_query="Summarize the incident notes.",
        ),
    )


def build_exception_message() -> ExceptionMessage:
    """Return a valid exception message for negative evaluation tests."""
    return ExceptionMessage(
        envelope=build_envelope(
            MessageType.FAP_EXCEPTION,
            sender_id="coordinator",
            recipient_id="participant_docs",
        ),
        payload=ExceptionPayload(
            code="participant.unavailable",
            message="The participant could not access its local source.",
        ),
    )


def test_evaluate_endpoint_returns_accept_for_supported_task_create() -> None:
    """Supported task-create messages should yield a canonical task-accept response."""
    inbound = build_task_create_message(["docs.lookup", "docs.summarize"])

    response = client.post("/evaluate", json=message_to_dict(inbound))

    body = response.json()
    assert response.status_code == 200
    assert body["envelope"]["message_type"] == "fap.task.accept"
    assert body["envelope"]["task_id"] == inbound.envelope.task_id
    assert body["envelope"]["run_id"] == inbound.envelope.run_id
    assert body["envelope"]["trace_id"] == inbound.envelope.trace_id
    assert body["envelope"]["sender_id"] == "participant_docs"
    assert body["envelope"]["recipient_id"] == "coordinator"
    assert body["payload"]["participant_id"] == "participant_docs"
    assert body["payload"]["accepted_capabilities"] == ["docs.lookup", "docs.summarize"]


def test_evaluate_endpoint_returns_reject_for_unsupported_task_create() -> None:
    """Unsupported requested capabilities should yield a canonical task-reject response."""
    inbound = build_task_create_message(["docs.lookup", "docs.translate"])

    response = client.post("/evaluate", json=message_to_dict(inbound))

    body = response.json()
    assert response.status_code == 200
    assert body["envelope"]["message_type"] == "fap.task.reject"
    assert body["payload"]["participant_id"] == "participant_docs"
    assert body["payload"]["retryable"] is False
    assert "docs.translate" in body["payload"]["reason"]


def test_evaluate_endpoint_rejects_non_task_create_messages() -> None:
    """Only task-create messages should be supported by the evaluation endpoint."""
    response = client.post("/evaluate", json=message_to_dict(build_exception_message()))

    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "code": "unsupported_evaluation_message",
            "message": "participant_docs can only evaluate 'fap.task.create' messages",
        }
    }


def test_evaluate_endpoint_rejects_malformed_known_kind_payload() -> None:
    """Malformed task-create payloads should reuse the shared parse error mapping."""
    raw_message = message_to_dict(build_task_create_message(["docs.search"]))
    payload = raw_message["payload"]
    assert isinstance(payload, dict)
    payload["title"] = "   "

    response = client.post("/evaluate", json=raw_message)

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "invalid_message",
            "message": "Failed to parse message kind 'fap.task.create'.",
        }
    }


def test_health_endpoint_still_works() -> None:
    """Participant docs health route should still be available."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "participant_docs"}

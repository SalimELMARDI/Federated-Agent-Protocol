"""Tests for coordinator run-state APIs."""

from __future__ import annotations

from fastapi.testclient import TestClient

from coordinator_api.main import create_app
from fap_core import message_to_dict
from fap_core.clocks import utc_now
from fap_core.enums import MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import (
    ExceptionMessage,
    ExceptionPayload,
    MessageEnvelope,
    TaskAcceptMessage,
    TaskAcceptPayload,
    TaskCreateMessage,
    TaskCreatePayload,
    TaskRejectMessage,
    TaskRejectPayload,
)


def build_client() -> TestClient:
    """Return a fresh coordinator test client with an isolated in-memory store."""
    return TestClient(create_app())


def build_create_message(*, run_id: str | None = None) -> TaskCreateMessage:
    """Return a valid task-create message for coordinator API tests."""
    shared_run_id = new_run_id() if run_id is None else run_id
    return TaskCreateMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_CREATE,
            task_id=new_task_id(),
            run_id=shared_run_id,
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id="participant_docs",
            domain_id="docs",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
        ),
        payload=TaskCreatePayload(
            title="Summarize notes",
            description="Create a redacted summary for coordinator review.",
            requested_capabilities=["docs.search"],
            input_query="Summarize the incident notes.",
        ),
    )


def build_accept_message(create_message: TaskCreateMessage, *, participant_id: str) -> TaskAcceptMessage:
    """Return a valid task-accept message derived from the created run."""
    return TaskAcceptMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_ACCEPT,
            task_id=create_message.envelope.task_id,
            run_id=create_message.envelope.run_id,
            message_id=new_message_id(),
            sender_id=participant_id,
            recipient_id="coordinator",
            domain_id=participant_id,
            trace_id=create_message.envelope.trace_id,
            timestamp=utc_now(),
        ),
        payload=TaskAcceptPayload(
            participant_id=participant_id,
            accepted_capabilities=["docs.search"],
        ),
    )


def build_reject_message(create_message: TaskCreateMessage, *, participant_id: str) -> TaskRejectMessage:
    """Return a valid task-reject message derived from the created run."""
    return TaskRejectMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_REJECT,
            task_id=create_message.envelope.task_id,
            run_id=create_message.envelope.run_id,
            message_id=new_message_id(),
            sender_id=participant_id,
            recipient_id="coordinator",
            domain_id=participant_id,
            trace_id=create_message.envelope.trace_id,
            timestamp=utc_now(),
        ),
        payload=TaskRejectPayload(
            participant_id=participant_id,
            reason="Unsupported capabilities requested: docs.translate",
            retryable=False,
        ),
    )


def build_exception_message() -> ExceptionMessage:
    """Return a valid untracked message type for coordinator tests."""
    return ExceptionMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_EXCEPTION,
            task_id=new_task_id(),
            run_id=new_run_id(),
            message_id=new_message_id(),
            sender_id="participant_docs",
            recipient_id="coordinator",
            domain_id="participant_docs",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
        ),
        payload=ExceptionPayload(
            code="participant.unavailable",
            message="The participant could not access its local source.",
        ),
    )


def test_post_create_then_get_run_returns_created_snapshot() -> None:
    """A created run should be retrievable through the run-state API."""
    client = build_client()
    create_message = build_create_message()

    post_response = client.post("/messages", json=message_to_dict(create_message))
    get_response = client.get(f"/runs/{create_message.envelope.run_id}")

    assert post_response.status_code == 202
    assert get_response.status_code == 200
    assert get_response.json() == {
        "run_id": create_message.envelope.run_id,
        "task_id": create_message.envelope.task_id,
        "status": "created",
        "created_message_id": create_message.envelope.message_id,
        "last_message_type": "fap.task.create",
        "message_count": 1,
        "accepted_participants": [],
        "rejected_participants": [],
        "completed_participants": [],
        "policy_attestations": [],
        "aggregate_submissions": [],
        "aggregate_results": [],
    }


def test_post_accept_after_create_updates_accepted_participants() -> None:
    """A task-accept message should update the stored run snapshot."""
    client = build_client()
    create_message = build_create_message()
    accept_message = build_accept_message(create_message, participant_id="participant_docs")

    client.post("/messages", json=message_to_dict(create_message))
    post_response = client.post("/messages", json=message_to_dict(accept_message))
    get_response = client.get(f"/runs/{create_message.envelope.run_id}")

    assert post_response.status_code == 202
    assert get_response.status_code == 200
    assert get_response.json()["accepted_participants"] == ["participant_docs"]
    assert get_response.json()["status"] == "decisions_recorded"


def test_post_reject_after_create_updates_rejected_participants() -> None:
    """A task-reject message should update the stored run snapshot."""
    client = build_client()
    create_message = build_create_message()
    reject_message = build_reject_message(create_message, participant_id="participant_docs")

    client.post("/messages", json=message_to_dict(create_message))
    post_response = client.post("/messages", json=message_to_dict(reject_message))
    get_response = client.get(f"/runs/{create_message.envelope.run_id}")

    assert post_response.status_code == 202
    assert get_response.status_code == 200
    assert get_response.json()["rejected_participants"] == [
        {
            "participant_id": "participant_docs",
            "reason": "Unsupported capabilities requested: docs.translate",
            "retryable": False,
        }
    ]
    assert get_response.json()["status"] == "decisions_recorded"


def test_duplicate_create_returns_run_already_exists() -> None:
    """Creating the same run twice should return a conflict."""
    client = build_client()
    create_message = build_create_message()

    first = client.post("/messages", json=message_to_dict(create_message))
    duplicate = client.post("/messages", json=message_to_dict(create_message))

    assert first.status_code == 202
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": {
            "code": "run_already_exists",
            "message": f"Run already exists: '{create_message.envelope.run_id}'",
        }
    }


def test_accept_for_unknown_run_returns_unknown_run() -> None:
    """Task-accept messages for unknown runs should return a conflict."""
    client = build_client()
    create_message = build_create_message()
    accept_message = build_accept_message(create_message, participant_id="participant_docs")

    response = client.post("/messages", json=message_to_dict(accept_message))

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "unknown_run",
            "message": f"Unknown run: '{accept_message.envelope.run_id}'",
        }
    }


def test_reject_for_unknown_run_returns_unknown_run() -> None:
    """Task-reject messages for unknown runs should return a conflict."""
    client = build_client()
    create_message = build_create_message()
    reject_message = build_reject_message(create_message, participant_id="participant_docs")

    response = client.post("/messages", json=message_to_dict(reject_message))

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "unknown_run",
            "message": f"Unknown run: '{reject_message.envelope.run_id}'",
        }
    }


def test_get_unknown_run_returns_not_found() -> None:
    """Unknown runs should return a stable 404 response."""
    client = build_client()
    unknown_run_id = new_run_id()

    response = client.get(f"/runs/{unknown_run_id}")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "run_not_found",
            "message": f"Run not found: '{unknown_run_id}'",
        }
    }


def test_valid_untracked_message_type_still_returns_accepted() -> None:
    """Tracked run state should ignore currently untracked but valid message types."""
    client = build_client()
    exception_message = build_exception_message()

    response = client.post("/messages", json=message_to_dict(exception_message))

    assert response.status_code == 202
    assert response.json() == {
        "status": "accepted",
        "message_type": "fap.exception",
        "message_id": exception_message.envelope.message_id,
        "task_id": exception_message.envelope.task_id,
        "run_id": exception_message.envelope.run_id,
    }


def test_health_endpoint_still_works() -> None:
    """Coordinator health route should remain available."""
    client = build_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "coordinator_api"}

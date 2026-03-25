"""Integration tests for coordinator durable persistence behavior."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from coordinator_api.db import ProtocolEvent, RunSnapshotRecord, create_session_factory
from coordinator_api.main import create_app as create_coordinator_app
from coordinator_api.service.persistence import PersistenceError, PersistenceService
from coordinator_api.service.state import RunSnapshot
from fap_core import message_to_dict
from fap_core.clocks import utc_now
from fap_core.enums import MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import MessageEnvelope, TaskCreateMessage, TaskCreatePayload
from participant_docs.main import create_app as create_participant_docs_app
from participant_logs.main import create_app as create_participant_logs_app


class FailingPersistenceService:
    """Persistence stub that always fails writes."""

    def persist_messages_and_snapshot(self, *_args: object, **_kwargs: object) -> None:
        raise PersistenceError("storage unavailable")

    def list_events_for_run(self, run_id: str) -> list[object]:
        raise PersistenceError(f"storage unavailable for {run_id}")

    def load_run_snapshot(self, run_id: str) -> RunSnapshot | None:
        del run_id
        return None

    def load_task_create_message(self, run_id: str) -> TaskCreateMessage | None:
        del run_id
        return None


def sqlite_url(path: Path) -> str:
    """Return a SQLite URL for a temporary database file."""
    return f"sqlite:///{path.as_posix()}"


def build_client(
    *,
    database_path: Path,
    participant_app: FastAPI | None = None,
    participant_logs_app: FastAPI | None = None,
    persistence_service: PersistenceService | None = None,
) -> TestClient:
    """Return a coordinator client backed by a temporary SQLite database."""
    transport = httpx.ASGITransport(app=participant_app) if participant_app is not None else None
    logs_transport = (
        httpx.ASGITransport(app=participant_logs_app)
        if participant_logs_app is not None
        else None
    )
    return TestClient(
        create_coordinator_app(
            participant_docs_transport=transport,
            participant_logs_transport=logs_transport,
            database_url=sqlite_url(database_path),
            persistence_service=persistence_service,
        )
    )


def build_task_create_message() -> TaskCreateMessage:
    """Return a valid task-create message for persistence API tests."""
    return TaskCreateMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_CREATE,
            task_id=new_task_id(),
            run_id=new_run_id(),
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id="participant_docs",
            domain_id="docs",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
        ),
        payload=TaskCreatePayload(
            title="Search local docs",
            description="Perform a deterministic local docs search.",
            requested_capabilities=["docs.search"],
            input_query="privacy",
        ),
    )


def build_logs_task_create_message() -> TaskCreateMessage:
    """Return a valid task-create message for participant_logs persistence tests."""
    return TaskCreateMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_CREATE,
            task_id=new_task_id(),
            run_id=new_run_id(),
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id="participant_logs",
            domain_id="logs",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
        ),
        payload=TaskCreatePayload(
            title="Query local logs",
            description="Perform a deterministic local logs search.",
            requested_capabilities=["logs.search"],
            input_query="privacy",
        ),
    )


def count_rows(database_path: Path) -> tuple[int, int]:
    """Return current durable protocol event and snapshot row counts."""
    session_factory = create_session_factory(database_url=sqlite_url(database_path))
    with session_factory() as session:
        event_count = session.query(ProtocolEvent).count()
        snapshot_count = session.query(RunSnapshotRecord).count()
    return event_count, snapshot_count


def test_post_messages_persists_one_event_and_one_snapshot(tmp_path: Path) -> None:
    """Tracked inbound coordinator messages should write through to durable storage."""
    database_path = tmp_path / "coordinator.db"
    client = build_client(database_path=database_path)
    create_message = build_task_create_message()

    response = client.post("/messages", json=message_to_dict(create_message))

    assert response.status_code == 202
    assert count_rows(database_path) == (1, 1)


def test_dispatch_to_evaluate_persists_the_returned_decision_event(tmp_path: Path) -> None:
    """Coordinator evaluate dispatch should persist the returned decision message."""
    database_path = tmp_path / "coordinator.db"
    client = build_client(
        database_path=database_path, participant_app=create_participant_docs_app()
    )
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs")

    assert response.status_code == 200
    assert count_rows(database_path) == (2, 1)


def test_dispatch_to_execute_persists_task_complete_policy_attest_and_aggregate_submit(
    tmp_path: Path,
) -> None:
    """Coordinator execute dispatch should persist governed outputs plus aggregate-submit."""
    database_path = tmp_path / "coordinator.db"
    client = build_client(
        database_path=database_path, participant_app=create_participant_docs_app()
    )
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute")

    assert response.status_code == 200
    assert count_rows(database_path) == (4, 1)


def test_dispatch_to_logs_execute_persists_task_complete_policy_attest_and_aggregate_submit(
    tmp_path: Path,
) -> None:
    """Coordinator execute dispatch should persist participant_logs governed outputs."""
    database_path = tmp_path / "coordinator.db"
    client = build_client(
        database_path=database_path,
        participant_logs_app=create_participant_logs_app(),
    )
    create_message = build_logs_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(
        f"/runs/{create_message.envelope.run_id}/dispatch/participant-logs/execute"
    )

    assert response.status_code == 200
    assert count_rows(database_path) == (4, 1)


def test_get_run_events_returns_persisted_events_in_order(tmp_path: Path) -> None:
    """The audit endpoint should return persisted events in durable insertion order."""
    database_path = tmp_path / "coordinator.db"
    client = build_client(
        database_path=database_path, participant_app=create_participant_docs_app()
    )
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs")
    response = client.get(f"/runs/{create_message.envelope.run_id}/events")

    body = response.json()
    assert response.status_code == 200
    assert [entry["message_type"] for entry in body] == [
        "fap.task.create",
        "fap.task.accept",
    ]
    assert body[0]["message_id"] == create_message.envelope.message_id
    assert "recorded_at" in body[0]


def test_fresh_app_instance_can_continue_run_from_persisted_db_state(tmp_path: Path) -> None:
    """A fresh coordinator app instance should inspect and execute a persisted run."""
    database_path = tmp_path / "coordinator.db"
    first_client = build_client(database_path=database_path)
    create_message = build_task_create_message()

    create_response = first_client.post("/messages", json=message_to_dict(create_message))
    assert create_response.status_code == 202

    second_client = build_client(
        database_path=database_path,
        participant_app=create_participant_docs_app(),
    )
    run_response = second_client.get(f"/runs/{create_message.envelope.run_id}")
    execute_response = second_client.post(
        f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute"
    )

    assert run_response.status_code == 200
    assert run_response.json()["status"] == "created"
    assert execute_response.status_code == 200
    assert execute_response.json()["task_complete"]["envelope"]["run_id"] == create_message.envelope.run_id


def test_persistence_failure_surfaces_as_http_500(tmp_path: Path) -> None:
    """Persistence errors should become stable 500 responses without changing protocol parsing."""
    database_path = tmp_path / "coordinator.db"
    client = build_client(
        database_path=database_path,
        persistence_service=cast(PersistenceService, FailingPersistenceService()),
    )
    create_message = build_task_create_message()

    response = client.post("/messages", json=message_to_dict(create_message))

    assert response.status_code == 500
    assert response.json() == {
        "detail": {
            "code": "persistence_failed",
            "message": "storage unavailable",
        }
    }


def test_health_endpoint_still_works(tmp_path: Path) -> None:
    """Coordinator health should remain available alongside durable persistence."""
    database_path = tmp_path / "coordinator.db"
    client = build_client(database_path=database_path)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "coordinator_api"}

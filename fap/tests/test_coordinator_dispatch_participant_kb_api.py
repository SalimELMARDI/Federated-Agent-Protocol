"""Tests for the coordinator->participant_kb dispatch API loop."""

from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.testclient import TestClient

from coordinator_api.main import create_app as create_coordinator_app
from fap_core import message_to_dict
from fap_core.clocks import utc_now
from fap_core.enums import MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import MessageEnvelope, TaskCreateMessage, TaskCreatePayload
from participant_kb.main import create_app as create_participant_kb_app


def build_client(participant_app: FastAPI, *, database_path: Path) -> TestClient:
    """Return a fresh coordinator client wired to an in-process participant_kb app."""
    transport = httpx.ASGITransport(app=participant_app)
    return TestClient(
        create_coordinator_app(
            participant_kb_transport=transport,
            database_url=f"sqlite:///{database_path.as_posix()}",
        )
    )


def build_task_create_message(requested_capabilities: list[str]) -> TaskCreateMessage:
    """Return a valid task-create message for dispatch API tests."""
    return TaskCreateMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_CREATE,
            task_id=new_task_id(),
            run_id=new_run_id(),
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id="participant_kb",
            domain_id="kb",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
        ),
        payload=TaskCreatePayload(
            title="Query local KB",
            description="Retrieve deterministic KB facts for coordinator review.",
            requested_capabilities=requested_capabilities,
            input_query="privacy",
        ),
    )


def create_non_200_participant_app() -> FastAPI:
    """Return a participant app stub that fails evaluation with a non-200 response."""
    app = FastAPI()

    @app.post("/evaluate")
    async def evaluate() -> JSONResponse:
        return JSONResponse({"detail": "nope"}, status_code=503)

    return app


def create_malformed_participant_app() -> FastAPI:
    """Return a participant app stub that responds with malformed JSON."""
    app = FastAPI()

    @app.post("/evaluate")
    async def evaluate() -> PlainTextResponse:
        return PlainTextResponse("not-json", status_code=200)

    return app


def test_dispatch_supported_create_returns_canonical_task_accept(tmp_path: Path) -> None:
    """Dispatching a supported task-create run should return a canonical task-accept."""
    client = build_client(create_participant_kb_app(), database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message(["kb.lookup", "kb.summarize"])

    create_response = client.post("/messages", json=message_to_dict(create_message))
    dispatch_response = client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-kb")

    body = dispatch_response.json()
    assert create_response.status_code == 202
    assert dispatch_response.status_code == 200
    assert body["envelope"]["message_type"] == "fap.task.accept"
    assert body["envelope"]["task_id"] == create_message.envelope.task_id
    assert body["envelope"]["run_id"] == create_message.envelope.run_id
    assert body["payload"]["participant_id"] == "participant_kb"
    assert body["payload"]["accepted_capabilities"] == ["kb.lookup", "kb.summarize"]


def test_dispatch_unsupported_create_returns_canonical_task_reject(tmp_path: Path) -> None:
    """Dispatching an unsupported task-create run should return a canonical task-reject."""
    client = build_client(create_participant_kb_app(), database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message(["kb.lookup", "kb.translate"])

    client.post("/messages", json=message_to_dict(create_message))
    dispatch_response = client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-kb")

    body = dispatch_response.json()
    assert dispatch_response.status_code == 200
    assert body["envelope"]["message_type"] == "fap.task.reject"
    assert body["payload"]["participant_id"] == "participant_kb"
    assert body["payload"]["retryable"] is False
    assert "kb.translate" in body["payload"]["reason"]


def test_get_run_reflects_accepted_participant_after_dispatch(tmp_path: Path) -> None:
    """The run snapshot should include accepted participants after accept dispatch."""
    client = build_client(create_participant_kb_app(), database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message(["kb.lookup"])

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-kb")
    run_response = client.get(f"/runs/{create_message.envelope.run_id}")
    events_response = client.get(f"/runs/{create_message.envelope.run_id}/events")

    assert run_response.status_code == 200
    assert run_response.json()["accepted_participants"] == ["participant_kb"]
    assert [entry["message_type"] for entry in events_response.json()] == [
        "fap.task.create",
        "fap.task.accept",
    ]


def test_get_run_reflects_rejected_participant_after_dispatch(tmp_path: Path) -> None:
    """The run snapshot should include structured rejections after reject dispatch."""
    client = build_client(create_participant_kb_app(), database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message(["kb.lookup", "kb.translate"])

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-kb")
    run_response = client.get(f"/runs/{create_message.envelope.run_id}")

    assert run_response.status_code == 200
    assert run_response.json()["rejected_participants"] == [
        {
            "participant_id": "participant_kb",
            "reason": "Unsupported capabilities requested: kb.translate",
            "retryable": False,
        }
    ]


def test_dispatch_for_unknown_run_returns_run_not_found(tmp_path: Path) -> None:
    """Dispatching an unknown run should return a stable 404 response."""
    client = build_client(create_participant_kb_app(), database_path=tmp_path / "coordinator.db")
    unknown_run_id = new_run_id()

    response = client.post(f"/runs/{unknown_run_id}/dispatch/participant-kb")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "run_not_found",
            "message": f"Run not found: '{unknown_run_id}'",
        }
    }


def test_downstream_non_200_becomes_participant_evaluation_failed(tmp_path: Path) -> None:
    """Non-200 downstream evaluation responses should map to a 502."""
    client = build_client(create_non_200_participant_app(), database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message(["kb.lookup"])

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-kb")

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "code": "participant_evaluation_failed",
            "message": "participant_kb evaluation failed with status 503",
        }
    }


def test_downstream_malformed_response_becomes_invalid_participant_response(tmp_path: Path) -> None:
    """Malformed downstream responses should map to a 502 invalid-response error."""
    client = build_client(create_malformed_participant_app(), database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message(["kb.lookup"])

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-kb")

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "code": "invalid_participant_response",
            "message": "participant_kb returned invalid JSON response",
        }
    }


def test_health_endpoint_still_works(tmp_path: Path) -> None:
    """Coordinator health route should remain available."""
    client = build_client(create_participant_kb_app(), database_path=tmp_path / "coordinator.db")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "coordinator_api"}

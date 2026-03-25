"""Tests for the coordinator->participant_kb execute-dispatch API loop."""

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


def build_task_create_message() -> TaskCreateMessage:
    """Return a valid task-create message for execute-dispatch API tests."""
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
            description="Perform a deterministic local KB search.",
            requested_capabilities=["kb.lookup"],
            input_query="privacy",
        ),
    )


def create_non_200_participant_app() -> FastAPI:
    """Return a participant app stub that fails execution with a non-200 response."""
    app = FastAPI()

    @app.post("/execute")
    async def execute() -> JSONResponse:
        return JSONResponse({"detail": "nope"}, status_code=503)

    return app


def create_malformed_participant_app() -> FastAPI:
    """Return a participant app stub that responds with malformed JSON for execution."""
    app = FastAPI()

    @app.post("/execute")
    async def execute() -> PlainTextResponse:
        return PlainTextResponse("not-json", status_code=200)

    return app


def test_dispatch_execute_returns_three_canonical_messages(tmp_path: Path) -> None:
    """Dispatching a stored run to execute should return task-complete, policy-attest, and aggregate-submit."""
    client = build_client(create_participant_kb_app(), database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message()

    create_response = client.post("/messages", json=message_to_dict(create_message))
    dispatch_response = client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-kb/execute")

    body = dispatch_response.json()
    assert create_response.status_code == 202
    assert dispatch_response.status_code == 200
    assert body["task_complete"]["envelope"]["message_type"] == "fap.task.complete"
    assert body["task_complete"]["envelope"]["task_id"] == create_message.envelope.task_id
    assert body["task_complete"]["payload"]["participant_id"] == "participant_kb"
    assert body["policy_attest"]["envelope"]["message_type"] == "fap.policy.attest"
    assert body["policy_attest"]["envelope"]["task_id"] == create_message.envelope.task_id
    assert body["policy_attest"]["envelope"]["run_id"] == create_message.envelope.run_id
    assert body["policy_attest"]["envelope"]["trace_id"] == create_message.envelope.trace_id
    assert body["policy_attest"]["payload"]["participant_id"] == "participant_kb"
    assert body["aggregate_submit"]["envelope"]["message_type"] == "fap.aggregate.submit"
    assert body["aggregate_submit"]["envelope"]["task_id"] == create_message.envelope.task_id
    assert body["aggregate_submit"]["envelope"]["run_id"] == create_message.envelope.run_id
    assert body["aggregate_submit"]["envelope"]["trace_id"] == create_message.envelope.trace_id
    assert body["aggregate_submit"]["payload"]["participant_id"] == "participant_kb"
    assert body["aggregate_submit"]["payload"]["provenance_ref"] == (
        body["policy_attest"]["envelope"]["message_id"]
    )


def test_get_run_reflects_completed_participants_after_execute_dispatch(tmp_path: Path) -> None:
    """The run snapshot should include structured completions after execute dispatch."""
    client = build_client(create_participant_kb_app(), database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-kb/execute")
    run_response = client.get(f"/runs/{create_message.envelope.run_id}")
    events_response = client.get(f"/runs/{create_message.envelope.run_id}/events")

    assert run_response.status_code == 200
    completed_participants = run_response.json()["completed_participants"]
    assert len(completed_participants) == 1
    assert completed_participants[0]["participant_id"] == "participant_kb"
    assert completed_participants[0]["status"] == "completed"
    assert completed_participants[0]["summary"] == "[SUMMARY ONLY] Matched KB entries: Privacy controls"
    assert completed_participants[0]["message_id"]
    assert completed_participants[0]["source_refs"][0]["source_id"] == "kb-001"
    assert [entry["message_type"] for entry in events_response.json()] == [
        "fap.task.create",
        "fap.task.complete",
        "fap.policy.attest",
        "fap.aggregate.submit",
    ]


def test_get_run_reflects_policy_attestations_after_execute_dispatch(tmp_path: Path) -> None:
    """The run snapshot should include structured policy attestations after execute dispatch."""
    client = build_client(create_participant_kb_app(), database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-kb/execute")
    run_response = client.get(f"/runs/{create_message.envelope.run_id}")

    assert run_response.status_code == 200
    policy_attestations = run_response.json()["policy_attestations"]
    assert len(policy_attestations) == 1
    assert policy_attestations[0]["participant_id"] == "participant_kb"
    assert policy_attestations[0]["policy_ref"] == "policy.kb.v0"
    assert policy_attestations[0]["original_privacy_class"] == "internal"
    assert policy_attestations[0]["applied_sharing_mode"] == "summary_only"
    assert policy_attestations[0]["transform_type"] == "summary_only"
    assert policy_attestations[0]["message_id"]


def test_get_run_reflects_aggregate_submissions_after_execute_dispatch(tmp_path: Path) -> None:
    """The run snapshot should include coordinator-generated aggregate submissions."""
    client = build_client(create_participant_kb_app(), database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-kb/execute")
    run_response = client.get(f"/runs/{create_message.envelope.run_id}")

    assert run_response.status_code == 200
    aggregate_submissions = run_response.json()["aggregate_submissions"]
    assert len(aggregate_submissions) == 1
    assert aggregate_submissions[0]["participant_id"] == "participant_kb"
    assert aggregate_submissions[0]["contribution_type"] == "summary"
    assert aggregate_submissions[0]["summary"] == (
        "[SUMMARY ONLY] Matched KB entries: Privacy controls"
    )
    assert aggregate_submissions[0]["provenance_ref"]
    assert aggregate_submissions[0]["message_id"]
    assert aggregate_submissions[0]["source_refs"][0]["source_id"] == "kb-001"


def test_dispatch_execute_for_unknown_run_returns_run_not_found(tmp_path: Path) -> None:
    """Execute-dispatching an unknown run should return a stable 404 response."""
    client = build_client(create_participant_kb_app(), database_path=tmp_path / "coordinator.db")
    unknown_run_id = new_run_id()

    response = client.post(f"/runs/{unknown_run_id}/dispatch/participant-kb/execute")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "run_not_found",
            "message": f"Run not found: '{unknown_run_id}'",
        }
    }


def test_downstream_non_200_becomes_participant_execution_failed(tmp_path: Path) -> None:
    """Non-200 downstream execution responses should map to a 502."""
    client = build_client(create_non_200_participant_app(), database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-kb/execute")

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "code": "participant_execution_failed",
            "message": "participant_kb execution failed with status 503",
        }
    }


def test_downstream_malformed_response_becomes_invalid_participant_execution_response(tmp_path: Path) -> None:
    """Malformed downstream execution responses should map to a 502 invalid-response error."""
    client = build_client(create_malformed_participant_app(), database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-kb/execute")

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "code": "invalid_participant_execution_response",
            "message": "participant_kb returned invalid JSON response",
        }
    }


def test_health_endpoint_still_works(tmp_path: Path) -> None:
    """Coordinator health route should remain available."""
    client = build_client(create_participant_kb_app(), database_path=tmp_path / "coordinator.db")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "coordinator_api"}

"""Tests for the coordinator one-shot orchestration API."""

from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from coordinator_api.main import create_app as create_coordinator_app
from fap_core import message_to_dict
from fap_core.clocks import utc_now
from fap_core.enums import MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import MessageEnvelope, TaskCreateMessage, TaskCreatePayload
from participant_docs.main import create_app as create_participant_docs_app
from participant_kb.main import create_app as create_participant_kb_app
from participant_logs.main import create_app as create_participant_logs_app


def build_client(
    *,
    database_path: Path,
    participant_docs_app: FastAPI | None = None,
    participant_kb_app: FastAPI | None = None,
    participant_logs_app: FastAPI | None = None,
) -> TestClient:
    """Return a coordinator client wired to in-process participant apps."""
    docs_app = create_participant_docs_app() if participant_docs_app is None else participant_docs_app
    kb_app = create_participant_kb_app() if participant_kb_app is None else participant_kb_app
    logs_app = (
        create_participant_logs_app() if participant_logs_app is None else participant_logs_app
    )
    return TestClient(
        create_coordinator_app(
            participant_docs_transport=httpx.ASGITransport(app=docs_app),
            participant_kb_transport=httpx.ASGITransport(app=kb_app),
            participant_logs_transport=httpx.ASGITransport(app=logs_app),
            database_url=f"sqlite:///{database_path.as_posix()}",
        )
    )


def build_task_create_message(*, requested_capabilities: list[str]) -> TaskCreateMessage:
    """Return a valid task-create message for orchestration API tests."""
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
            title="Orchestrate governed federation",
            description="Coordinate a deterministic multi-participant run.",
            requested_capabilities=requested_capabilities,
            input_query="privacy",
        ),
    )


def create_failing_docs_app() -> FastAPI:
    """Return a participant_docs stub that fails evaluation."""
    app = FastAPI()

    @app.post("/evaluate")
    async def evaluate() -> JSONResponse:
        return JSONResponse({"detail": "nope"}, status_code=503)

    return app


def create_identity_mismatch_docs_app() -> FastAPI:
    """Return a participant_docs stub that responds with the wrong sender identity."""
    app = FastAPI()

    @app.post("/evaluate")
    async def evaluate() -> dict[str, object]:
        return {
            "envelope": {
                "protocol": "FAP",
                "version": "0.1",
                "message_type": "fap.task.accept",
                "task_id": new_task_id(),
                "run_id": new_run_id(),
                "message_id": new_message_id(),
                "sender_id": "participant_kb",
                "recipient_id": "coordinator",
                "domain_id": "participant_kb",
                "trace_id": new_trace_id(),
                "timestamp": utc_now().isoformat(),
                "governance": None,
            },
            "payload": {
                "participant_id": "participant_docs",
                "accepted_capabilities": ["docs.lookup"],
                "constraints": [],
                "estimated_confidence": None,
                "note": None,
            },
        }

    return app


def test_create_run_then_orchestrate_returns_final_canonical_aggregate_result(tmp_path: Path) -> None:
    """One-shot orchestration should return a canonical aggregate result payload."""
    client = build_client(database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message(requested_capabilities=[])

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/orchestrate/summary-merge")

    body = response.json()
    assert response.status_code == 200
    assert body["run_id"] == create_message.envelope.run_id
    assert body["aggregate_result"]["envelope"]["message_type"] == "fap.aggregate.result"


def test_all_participants_execute_and_aggregate_includes_all_summaries(tmp_path: Path) -> None:
    """Empty requested capabilities should allow all participants to contribute."""
    client = build_client(database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message(requested_capabilities=[])

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/orchestrate/summary-merge")

    assert response.status_code == 200
    assert response.json()["aggregate_result"]["payload"]["final_answer"] == (
        "[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo\n"
        "[participant_kb] [SUMMARY ONLY] Matched KB entries: Privacy controls\n"
        "[participant_logs] [SUMMARY ONLY] Matched log events: privacy-monitor"
    )
    assert [
        source_ref["source_id"]
        for source_ref in response.json()["aggregate_result"]["payload"]["source_refs"]
    ] == ["doc-002", "kb-001", "log-002"]


def test_one_participant_rejects_and_aggregate_still_succeeds(tmp_path: Path) -> None:
    """Rejected participants should be skipped while accepted participants still execute."""
    client = build_client(database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message(requested_capabilities=["docs.search"])

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/orchestrate/summary-merge")

    body = response.json()
    assert response.status_code == 200
    assert [entry["accepted"] for entry in body["evaluations"]] == [True, False, False]
    assert [entry["executed"] for entry in body["executions"]] == [True, False, False]
    assert body["aggregate_result"]["payload"]["participant_count"] == 1
    assert [source_ref["source_id"] for source_ref in body["aggregate_result"]["payload"]["source_refs"]] == [
        "doc-002"
    ]


def test_all_participants_reject_returns_no_executable_participants(tmp_path: Path) -> None:
    """If all participants reject evaluation, orchestration should return a stable 409."""
    client = build_client(database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message(requested_capabilities=["docs.translate"])

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/orchestrate/summary-merge")

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "no_executable_participants",
            "message": f"No participants accepted execution for run: '{create_message.envelope.run_id}'",
        }
    }


def test_unknown_run_returns_run_not_found(tmp_path: Path) -> None:
    """Unknown runs should return a stable 404 response."""
    client = build_client(database_path=tmp_path / "coordinator.db")
    unknown_run_id = new_run_id()

    response = client.post(f"/runs/{unknown_run_id}/orchestrate/summary-merge")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "run_not_found",
            "message": f"Run not found: '{unknown_run_id}'",
        }
    }


def test_downstream_participant_failure_returns_participant_orchestration_failed(
    tmp_path: Path,
) -> None:
    """Participant dispatch failures should become orchestration 502 responses."""
    client = build_client(
        database_path=tmp_path / "coordinator.db",
        participant_docs_app=create_failing_docs_app(),
    )
    create_message = build_task_create_message(requested_capabilities=[])

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/orchestrate/summary-merge")

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "code": "participant_orchestration_failed",
            "message": "participant_docs evaluation failed with status 503",
        }
    }


def test_identity_mismatch_returns_participant_identity_mismatch(tmp_path: Path) -> None:
    """Identity mismatch failures should surface with a dedicated trust error code."""
    client = build_client(
        database_path=tmp_path / "coordinator.db",
        participant_docs_app=create_identity_mismatch_docs_app(),
    )
    create_message = build_task_create_message(requested_capabilities=[])

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/orchestrate/summary-merge")

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "code": "participant_identity_mismatch",
            "message": (
                "participant_docs returned evaluation response identity mismatch: expected "
                "sender_id/domain_id/recipient_id 'participant_docs'/'participant_docs'/'coordinator', "
                "got 'participant_kb'/'participant_kb'/'coordinator'"
            ),
        }
    }


def test_get_run_reflects_final_aggregate_result_after_orchestration(tmp_path: Path) -> None:
    """The run snapshot should show aggregate submissions and the final aggregate result."""
    client = build_client(database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message(requested_capabilities=[])

    client.post("/messages", json=message_to_dict(create_message))
    orchestrate_response = client.post(
        f"/runs/{create_message.envelope.run_id}/orchestrate/summary-merge"
    )
    run_response = client.get(f"/runs/{create_message.envelope.run_id}")

    assert orchestrate_response.status_code == 200
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "aggregated_recorded"
    assert len(run_response.json()["aggregate_submissions"]) == 3
    assert len(run_response.json()["aggregate_results"]) == 1
    assert [source_ref["source_id"] for source_ref in run_response.json()["aggregate_results"][0]["source_refs"]] == [
        "doc-002",
        "kb-001",
        "log-002",
    ]


def test_get_run_events_includes_persisted_evaluation_execution_attestation_and_aggregate_events(
    tmp_path: Path,
) -> None:
    """One-shot orchestration should persist all returned events in durable order."""
    client = build_client(database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message(requested_capabilities=[])

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/orchestrate/summary-merge")
    events_response = client.get(f"/runs/{create_message.envelope.run_id}/events")

    assert events_response.status_code == 200
    assert [entry["message_type"] for entry in events_response.json()] == [
        "fap.task.create",
        "fap.task.accept",
        "fap.task.accept",
        "fap.task.accept",
        "fap.task.complete",
        "fap.policy.attest",
        "fap.aggregate.submit",
        "fap.task.complete",
        "fap.policy.attest",
        "fap.aggregate.submit",
        "fap.task.complete",
        "fap.policy.attest",
        "fap.aggregate.submit",
        "fap.aggregate.result",
    ]


def test_health_endpoint_still_works(tmp_path: Path) -> None:
    """Coordinator health route should remain available."""
    client = build_client(database_path=tmp_path / "coordinator.db")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "coordinator_api"}

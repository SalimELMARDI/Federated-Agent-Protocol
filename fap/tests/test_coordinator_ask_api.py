"""Tests for the coordinator user-facing ask API wrapper."""

from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from coordinator_api.main import create_app as create_coordinator_app
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
    logs_app = create_participant_logs_app() if participant_logs_app is None else participant_logs_app
    return TestClient(
        create_coordinator_app(
            participant_docs_transport=httpx.ASGITransport(app=docs_app),
            participant_kb_transport=httpx.ASGITransport(app=kb_app),
            participant_logs_transport=httpx.ASGITransport(app=logs_app),
            database_url=f"sqlite:///{database_path.as_posix()}",
        )
    )


def create_failing_docs_app() -> FastAPI:
    """Return a participant_docs stub that fails evaluation."""
    app = FastAPI()

    @app.post("/evaluate")
    async def evaluate() -> JSONResponse:
        return JSONResponse({"detail": "nope"}, status_code=503)

    return app


def test_ask_runs_full_three_participant_flow_and_returns_traceable_result(tmp_path: Path) -> None:
    """The ask wrapper should create, orchestrate, and return the final aggregate result."""
    client = build_client(database_path=tmp_path / "coordinator.db")

    response = client.post("/ask", json={"query": "privacy"})

    body = response.json()
    assert response.status_code == 200
    assert body["run_id"]
    assert body["task_id"]
    assert body["created_message_id"]
    assert body["final_answer"] == (
        "[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo\n"
        "[participant_kb] [SUMMARY ONLY] Matched KB entries: Privacy controls\n"
        "[participant_logs] [SUMMARY ONLY] Matched log events: privacy-monitor"
    )
    assert body["aggregate_result"]["envelope"]["message_type"] == "fap.aggregate.result"
    assert [source_ref["source_id"] for source_ref in body["source_refs"]] == [
        "doc-002",
        "kb-001",
        "log-002",
    ]
    assert [entry["participant"] for entry in body["evaluations"]] == [
        "participant_docs",
        "participant_kb",
        "participant_logs",
    ]
    assert [entry["executed"] for entry in body["executions"]] == [True, True, True]
    assert body["run_path"] == f"/runs/{body['run_id']}"
    assert body["events_path"] == f"/runs/{body['run_id']}/events"

    run_response = client.get(body["run_path"])
    events_response = client.get(body["events_path"])

    assert run_response.status_code == 200
    assert run_response.json()["status"] == "aggregated_recorded"
    assert len(run_response.json()["aggregate_results"]) == 1
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


def test_ask_can_scope_to_one_participant(tmp_path: Path) -> None:
    """Requested capabilities should let the ask wrapper run a narrower federated flow."""
    client = build_client(database_path=tmp_path / "coordinator.db")

    response = client.post(
        "/ask",
        json={"query": "privacy", "requested_capabilities": ["docs.search"]},
    )

    body = response.json()
    assert response.status_code == 200
    assert [entry["accepted"] for entry in body["evaluations"]] == [True, False, False]
    assert [entry["executed"] for entry in body["executions"]] == [True, False, False]
    assert body["aggregate_result"]["payload"]["participant_count"] == 1
    assert body["final_answer"] == (
        "[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo"
    )
    assert [source_ref["source_id"] for source_ref in body["source_refs"]] == ["doc-002"]


def test_ask_rejects_blank_query_via_request_validation(tmp_path: Path) -> None:
    """The user-facing wrapper should reject empty plain-language requests."""
    client = build_client(database_path=tmp_path / "coordinator.db")

    response = client.post("/ask", json={"query": "   "})

    assert response.status_code == 422


def test_ask_surfaces_participant_orchestration_failures(tmp_path: Path) -> None:
    """Participant runtime failures should surface as 502 responses."""
    client = build_client(
        database_path=tmp_path / "coordinator.db",
        participant_docs_app=create_failing_docs_app(),
    )

    response = client.post("/ask", json={"query": "privacy"})

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "code": "participant_orchestration_failed",
            "message": "participant_docs evaluation failed with status 503",
        }
    }


def test_health_endpoint_still_works(tmp_path: Path) -> None:
    """Coordinator health should remain available alongside the ask wrapper."""
    client = build_client(database_path=tmp_path / "coordinator.db")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "coordinator_api"}

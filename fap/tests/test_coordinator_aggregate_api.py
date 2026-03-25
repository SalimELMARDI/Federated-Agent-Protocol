"""Tests for the coordinator aggregate runtime API."""

from __future__ import annotations

from pathlib import Path

import httpx
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


def build_client(*, database_path: Path) -> TestClient:
    """Return a coordinator client wired to in-process participant apps."""
    return TestClient(
        create_coordinator_app(
            participant_docs_transport=httpx.ASGITransport(app=create_participant_docs_app()),
            participant_kb_transport=httpx.ASGITransport(app=create_participant_kb_app()),
            participant_logs_transport=httpx.ASGITransport(app=create_participant_logs_app()),
            database_url=f"sqlite:///{database_path.as_posix()}",
        )
    )


def build_task_create_message() -> TaskCreateMessage:
    """Return a valid task-create message for aggregation API tests."""
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
            title="Aggregate governed outputs",
            description="Merge deterministic participant summaries.",
            requested_capabilities=["docs.search"],
            input_query="privacy",
        ),
    )


def test_docs_execute_then_aggregate_returns_canonical_aggregate_result(tmp_path: Path) -> None:
    """A single completed participant should aggregate into a canonical result message."""
    client = build_client(database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute")
    response = client.post(f"/runs/{create_message.envelope.run_id}/aggregate/summary-merge")

    body = response.json()
    assert response.status_code == 200
    assert body["envelope"]["message_type"] == "fap.aggregate.result"
    assert body["envelope"]["task_id"] == create_message.envelope.task_id
    assert body["envelope"]["run_id"] == create_message.envelope.run_id
    assert body["payload"]["aggregation_mode"] == "summary_merge"
    assert body["payload"]["participant_count"] == 1
    assert body["payload"]["final_answer"] == (
        "[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo"
    )
    assert body["payload"]["source_refs"] == [
        {
            "participant_id": "participant_docs",
            "source_id": "doc-002",
            "source_title": "Privacy Policy Memo",
            "source_path": body["payload"]["source_refs"][0]["source_path"],
        }
    ]
    assert body["payload"]["source_refs"][0]["source_path"].endswith(
        "doc-002__privacy-policy-memo.json"
    )


def test_docs_kb_and_logs_execute_then_aggregate_returns_deterministic_merged_answer(
    tmp_path: Path,
) -> None:
    """Three participant completions should merge in stable participant order."""
    client = build_client(database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-logs/execute")
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-kb/execute")
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute")
    response = client.post(f"/runs/{create_message.envelope.run_id}/aggregate/summary-merge")

    assert response.status_code == 200
    assert response.json()["payload"]["final_answer"] == (
        "[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo\n"
        "[participant_kb] [SUMMARY ONLY] Matched KB entries: Privacy controls\n"
        "[participant_logs] [SUMMARY ONLY] Matched log events: privacy-monitor"
    )
    assert response.json()["payload"]["participant_count"] == 3
    assert [source_ref["source_id"] for source_ref in response.json()["payload"]["source_refs"]] == [
        "doc-002",
        "kb-001",
        "log-002",
    ]


def test_get_run_reflects_aggregate_results_after_aggregation(tmp_path: Path) -> None:
    """The run snapshot should include aggregate submissions and aggregate results."""
    client = build_client(database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute")
    aggregate_response = client.post(f"/runs/{create_message.envelope.run_id}/aggregate/summary-merge")
    run_response = client.get(f"/runs/{create_message.envelope.run_id}")

    assert aggregate_response.status_code == 200
    assert run_response.status_code == 200
    aggregate_submissions = run_response.json()["aggregate_submissions"]
    aggregate_results = run_response.json()["aggregate_results"]
    assert len(aggregate_submissions) == 1
    assert aggregate_submissions[0]["participant_id"] == "participant_docs"
    assert aggregate_submissions[0]["contribution_type"] == "summary"
    assert aggregate_submissions[0]["summary"] == (
        "[SUMMARY ONLY] Matched docs: Privacy Policy Memo"
    )
    assert aggregate_submissions[0]["source_refs"][0]["source_id"] == "doc-002"
    assert len(aggregate_results) == 1
    assert aggregate_results[0]["aggregation_mode"] == "summary_merge"
    assert aggregate_results[0]["participant_count"] == 1
    assert aggregate_results[0]["source_refs"][0]["source_id"] == "doc-002"
    assert aggregate_results[0]["message_id"]


def test_get_run_events_includes_persisted_aggregate_result_event(tmp_path: Path) -> None:
    """Execute dispatch and aggregate should persist aggregate-submit before aggregate-result."""
    client = build_client(database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute")
    client.post(f"/runs/{create_message.envelope.run_id}/aggregate/summary-merge")
    events_response = client.get(f"/runs/{create_message.envelope.run_id}/events")

    assert events_response.status_code == 200
    assert [entry["message_type"] for entry in events_response.json()] == [
        "fap.task.create",
        "fap.task.complete",
        "fap.policy.attest",
        "fap.aggregate.submit",
        "fap.aggregate.result",
    ]


def test_aggregate_for_unknown_run_returns_run_not_found(tmp_path: Path) -> None:
    """Unknown runs should return a stable 404 response."""
    client = build_client(database_path=tmp_path / "coordinator.db")
    unknown_run_id = new_run_id()

    response = client.post(f"/runs/{unknown_run_id}/aggregate/summary-merge")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "run_not_found",
            "message": f"Run not found: '{unknown_run_id}'",
        }
    }


def test_aggregate_with_no_completed_participants_returns_conflict(tmp_path: Path) -> None:
    """Aggregation should fail cleanly when no completions have been recorded."""
    client = build_client(database_path=tmp_path / "coordinator.db")
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/aggregate/summary-merge")

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "no_completed_participants",
            "message": (
                f"No completed participant results available for run: "
                f"'{create_message.envelope.run_id}'"
            ),
        }
    }


def test_health_endpoint_still_works(tmp_path: Path) -> None:
    """Coordinator health route should remain available."""
    client = build_client(database_path=tmp_path / "coordinator.db")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "coordinator_api"}

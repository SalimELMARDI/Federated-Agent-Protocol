"""Tests for the minimal external FAP Python client."""

from __future__ import annotations

import httpx
import pytest

from fap_client import FAPClient, FAPClientHTTPError


def build_client(handler: httpx.MockTransport) -> FAPClient:
    """Return a client wired to a mocked coordinator transport."""
    return FAPClient(
        "http://coordinator.test",
        client=httpx.Client(transport=handler),
    )


def test_ask_returns_typed_response() -> None:
    """The client should parse `/ask` into a typed response model."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/ask"
        assert request.read() == b'{"query":"privacy"}'
        return httpx.Response(
            200,
            json={
                "run_id": "run_demo",
                "task_id": "task_demo",
                "created_message_id": "msg_demo",
                "final_answer": "[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo",
                "source_refs": [
                    {
                        "participant_id": "participant_docs",
                        "source_id": "doc-002",
                        "source_title": "Privacy Policy Memo",
                        "source_path": "examples/local_docs/data/doc-002__privacy-policy-memo.json",
                    }
                ],
                "aggregate_result": {
                    "envelope": {"message_type": "fap.aggregate.result"},
                    "payload": {"participant_count": 1},
                },
                "evaluations": [
                    {
                        "participant": "participant_docs",
                        "message_type": "fap.task.accept",
                        "accepted": True,
                    }
                ],
                "executions": [
                    {
                        "participant": "participant_docs",
                        "executed": True,
                        "message_type": "fap.task.complete",
                    }
                ],
                "run_path": "/runs/run_demo",
                "events_path": "/runs/run_demo/events",
            },
        )

    with build_client(httpx.MockTransport(handler)) as client:
        response = client.ask("privacy")

    assert response.run_id == "run_demo"
    assert response.evaluations[0].participant == "participant_docs"
    assert response.executions[0].executed is True
    assert response.source_refs[0].source_id == "doc-002"


def test_get_run_returns_typed_snapshot() -> None:
    """The client should parse coordinator run snapshots into a typed model."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/runs/run_demo"
        return httpx.Response(
            200,
            json={
                "run_id": "run_demo",
                "task_id": "task_demo",
                "status": "aggregated_recorded",
                "created_message_id": "msg_demo",
                "last_message_type": "fap.aggregate.result",
                "message_count": 14,
                "accepted_participants": [
                    "participant_docs",
                    "participant_kb",
                    "participant_logs",
                ],
                "rejected_participants": [],
                "completed_participants": [],
                "policy_attestations": [],
                "aggregate_submissions": [],
                "aggregate_results": [],
            },
        )

    with build_client(httpx.MockTransport(handler)) as client:
        response = client.get_run("run_demo")

    assert response.run_id == "run_demo"
    assert response.status == "aggregated_recorded"
    assert response.accepted_participants == [
        "participant_docs",
        "participant_kb",
        "participant_logs",
    ]


def test_get_events_returns_typed_event_wrapper() -> None:
    """The client should parse coordinator event lists into a typed wrapper."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/runs/run_demo/events"
        return httpx.Response(
            200,
            json=[
                {
                    "message_id": "msg_1",
                    "message_type": "fap.task.create",
                    "sender_id": "coordinator",
                    "recipient_id": "participant_docs",
                    "recorded_at": "2026-03-25T12:00:00Z",
                },
                {
                    "message_id": "msg_2",
                    "message_type": "fap.aggregate.result",
                    "sender_id": "coordinator",
                    "recipient_id": "fap_agent",
                    "recorded_at": "2026-03-25T12:00:10Z",
                },
            ],
        )

    with build_client(httpx.MockTransport(handler)) as client:
        response = client.get_events("run_demo")

    assert response.run_id == "run_demo"
    assert response.message_types() == [
        "fap.task.create",
        "fap.aggregate.result",
    ]


def test_non_200_responses_raise_client_http_error() -> None:
    """Unexpected coordinator HTTP statuses should raise a typed client error."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ask"
        return httpx.Response(
            502,
            json={
                "detail": {
                    "code": "participant_orchestration_failed",
                    "message": "participant_docs evaluation failed with status 503",
                }
            },
        )

    with build_client(httpx.MockTransport(handler)) as client:
        with pytest.raises(FAPClientHTTPError) as exc_info:
            client.ask("privacy")

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == {
        "detail": {
            "code": "participant_orchestration_failed",
            "message": "participant_docs evaluation failed with status 503",
        }
    }

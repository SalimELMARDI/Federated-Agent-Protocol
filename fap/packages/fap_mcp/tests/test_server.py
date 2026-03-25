"""Tests for the minimal FAP MCP server wrapper."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from fap_client.models import (
    AskResponse,
    EvaluationRecord,
    ExecutionRecord,
    PersistedEventSummary,
    RunEventsResponse,
    RunSnapshotResponse,
)
from fap_mcp import build_tool_handlers, create_fap_mcp_server


class FakeFAPClient:
    """Minimal fake client used to validate MCP tool delegation."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def ask(self, question: str) -> AskResponse:
        self.calls.append(("ask", question))
        return AskResponse(
            run_id="run_demo",
            task_id="task_demo",
            created_message_id="msg_create",
            final_answer="[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo",
            aggregate_result={
                "envelope": {"message_type": "fap.aggregate.result"},
                "payload": {"participant_count": 1},
            },
            evaluations=[
                EvaluationRecord(
                    participant="participant_docs",
                    message_type="fap.task.accept",
                    accepted=True,
                )
            ],
            executions=[
                ExecutionRecord(
                    participant="participant_docs",
                    executed=True,
                    message_type="fap.task.complete",
                )
            ],
            run_path="/runs/run_demo",
            events_path="/runs/run_demo/events",
        )

    def get_run(self, run_id: str) -> RunSnapshotResponse:
        self.calls.append(("get_run", run_id))
        return RunSnapshotResponse(
            run_id=run_id,
            task_id="task_demo",
            status="aggregated_recorded",
            created_message_id="msg_create",
            last_message_type="fap.aggregate.result",
            message_count=14,
            accepted_participants=[
                "participant_docs",
                "participant_kb",
                "participant_logs",
            ],
            rejected_participants=[],
            completed_participants=[],
            policy_attestations=[],
            aggregate_submissions=[],
            aggregate_results=[],
        )

    def get_events(self, run_id: str) -> RunEventsResponse:
        self.calls.append(("get_events", run_id))
        return RunEventsResponse(
            run_id=run_id,
            events=[
                PersistedEventSummary(
                    message_id="msg_create",
                    message_type="fap.task.create",
                    sender_id="coordinator",
                    recipient_id="participant_docs",
                    recorded_at=datetime(2026, 3, 25, 12, 0, tzinfo=UTC),
                )
            ],
        )

    def submit_message(self, message: Mapping[str, object]) -> dict[str, object]:
        self.calls.append(("submit_message", dict(message)))
        return {"status": "accepted", "message_type": "fap.task.create"}


def test_tool_handlers_delegate_to_fap_client() -> None:
    """Direct tool handlers should call the underlying client methods."""
    client = FakeFAPClient()
    handlers = build_tool_handlers(client)

    ask_result = handlers.fap_ask("privacy")
    run_result = handlers.fap_get_run("run_demo")
    events_result = handlers.fap_get_events("run_demo")
    submit_result = handlers.fap_submit_message({"envelope": {}, "payload": {}})

    assert ask_result["run_id"] == "run_demo"
    assert run_result["status"] == "aggregated_recorded"
    assert events_result["run_id"] == "run_demo"
    assert submit_result["status"] == "accepted"
    assert client.calls == [
        ("ask", "privacy"),
        ("get_run", "run_demo"),
        ("get_events", "run_demo"),
        ("submit_message", {"envelope": {}, "payload": {}}),
    ]


@pytest.mark.asyncio
async def test_server_exposes_expected_tools() -> None:
    """The MCP server should register the expected FAP tools."""
    server = create_fap_mcp_server(client=FakeFAPClient())

    tool_names = {tool.name for tool in await server.list_tools()}
    assert tool_names == {
        "fap_ask",
        "fap_get_run",
        "fap_get_events",
        "fap_submit_message",
    }

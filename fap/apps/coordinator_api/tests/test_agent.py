"""Tests for the thin user-facing coordinator agent wrapper."""

from __future__ import annotations

from collections.abc import Sequence

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from coordinator_api.service.agent import AgentAskRequest, run_agent_request_summary_merge
from coordinator_api.service.orchestration import ParticipantOrchestrationFailedError
from coordinator_api.service.persistence import PersistedEventSummary
from coordinator_api.service.state import RunSnapshot
from coordinator_api.service.store import InMemoryRunStore
from fap_core.messages import SupportedMessage, TaskCreateMessage
from participant_docs.main import create_app as create_participant_docs_app
from participant_kb.main import create_app as create_participant_kb_app
from participant_logs.main import create_app as create_participant_logs_app


class RecordingPersistenceService:
    """In-memory persistence stub for agent wrapper tests."""

    def __init__(self) -> None:
        self.recorded_batches: list[list[str]] = []

    def persist_messages_and_snapshot(
        self, messages: Sequence[SupportedMessage], **_kwargs: object
    ) -> None:
        self.recorded_batches.append(
            [message.envelope.message_type.value for message in messages]
        )

    def list_events_for_run(self, run_id: str) -> list[PersistedEventSummary]:
        return []

    def load_run_snapshot(self, run_id: str) -> RunSnapshot | None:
        del run_id
        return None

    def load_task_create_message(self, run_id: str) -> TaskCreateMessage | None:
        del run_id
        return None


def create_failing_docs_app() -> FastAPI:
    """Return a participant_docs stub that fails evaluation."""
    app = FastAPI()

    @app.post("/evaluate")
    async def evaluate() -> JSONResponse:
        return JSONResponse({"detail": "nope"}, status_code=503)

    return app


@pytest.mark.anyio
async def test_agent_request_runs_full_three_participant_orchestration() -> None:
    """Default empty capabilities should execute docs, kb, and logs through the wrapper."""
    store = InMemoryRunStore()
    persistence = RecordingPersistenceService()

    result = await run_agent_request_summary_merge(
        AgentAskRequest(query="privacy"),
        store=store,
        persistence_service=persistence,
        participant_docs_evaluate_url="http://participant-docs/evaluate",
        participant_docs_execute_url="http://participant-docs/execute",
        participant_docs_transport=httpx.ASGITransport(app=create_participant_docs_app()),
        participant_kb_evaluate_url="http://participant-kb/evaluate",
        participant_kb_execute_url="http://participant-kb/execute",
        participant_kb_transport=httpx.ASGITransport(app=create_participant_kb_app()),
        participant_logs_evaluate_url="http://participant-logs/evaluate",
        participant_logs_execute_url="http://participant-logs/execute",
        participant_logs_transport=httpx.ASGITransport(app=create_participant_logs_app()),
    )

    assert result.run_id.startswith("run_")
    assert result.task_id.startswith("task_")
    assert result.created_message_id.startswith("msg_")
    assert [entry.participant for entry in result.orchestration.evaluations] == [
        "participant_docs",
        "participant_kb",
        "participant_logs",
    ]
    assert [entry.accepted for entry in result.orchestration.evaluations] == [True, True, True]
    assert [entry.executed for entry in result.orchestration.executions] == [True, True, True]
    assert result.orchestration.aggregate_result.payload.participant_count == 3
    assert result.orchestration.aggregate_result.payload.final_answer == (
        "[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo\n"
        "[participant_kb] [SUMMARY ONLY] Matched KB entries: Privacy controls\n"
        "[participant_logs] [SUMMARY ONLY] Matched log events: privacy-monitor"
    )
    assert [source_ref.source_id for source_ref in result.orchestration.aggregate_result.payload.source_refs] == [
        "doc-002",
        "kb-001",
        "log-002",
    ]
    assert persistence.recorded_batches == [
        ["fap.task.create"],
        ["fap.task.accept"],
        ["fap.task.accept"],
        ["fap.task.accept"],
        ["fap.task.complete", "fap.policy.attest", "fap.aggregate.submit"],
        ["fap.task.complete", "fap.policy.attest", "fap.aggregate.submit"],
        ["fap.task.complete", "fap.policy.attest", "fap.aggregate.submit"],
        ["fap.aggregate.result"],
    ]


@pytest.mark.anyio
async def test_agent_request_can_scope_to_one_participant_via_requested_capabilities() -> None:
    """Capability scoping should let the wrapper orchestrate a one-participant run."""
    store = InMemoryRunStore()
    persistence = RecordingPersistenceService()

    result = await run_agent_request_summary_merge(
        AgentAskRequest(query="privacy", requested_capabilities=["docs.search"]),
        store=store,
        persistence_service=persistence,
        participant_docs_evaluate_url="http://participant-docs/evaluate",
        participant_docs_execute_url="http://participant-docs/execute",
        participant_docs_transport=httpx.ASGITransport(app=create_participant_docs_app()),
        participant_kb_evaluate_url="http://participant-kb/evaluate",
        participant_kb_execute_url="http://participant-kb/execute",
        participant_kb_transport=httpx.ASGITransport(app=create_participant_kb_app()),
        participant_logs_evaluate_url="http://participant-logs/evaluate",
        participant_logs_execute_url="http://participant-logs/execute",
        participant_logs_transport=httpx.ASGITransport(app=create_participant_logs_app()),
    )

    assert [entry.accepted for entry in result.orchestration.evaluations] == [True, False, False]
    assert [entry.executed for entry in result.orchestration.executions] == [True, False, False]
    assert result.orchestration.aggregate_result.payload.participant_count == 1
    assert result.orchestration.aggregate_result.payload.final_answer == (
        "[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo"
    )
    assert [source_ref.source_id for source_ref in result.orchestration.aggregate_result.payload.source_refs] == [
        "doc-002"
    ]


@pytest.mark.anyio
async def test_agent_request_surfaces_participant_failures_cleanly() -> None:
    """Participant orchestration failures should bubble through the wrapper."""
    store = InMemoryRunStore()
    persistence = RecordingPersistenceService()

    with pytest.raises(
        ParticipantOrchestrationFailedError,
        match="participant_docs evaluation failed with status 503",
    ):
        await run_agent_request_summary_merge(
            AgentAskRequest(query="privacy"),
            store=store,
            persistence_service=persistence,
            participant_docs_evaluate_url="http://participant-docs/evaluate",
            participant_docs_execute_url="http://participant-docs/execute",
            participant_docs_transport=httpx.ASGITransport(app=create_failing_docs_app()),
            participant_kb_evaluate_url="http://participant-kb/evaluate",
            participant_kb_execute_url="http://participant-kb/execute",
            participant_kb_transport=httpx.ASGITransport(app=create_participant_kb_app()),
            participant_logs_evaluate_url="http://participant-logs/evaluate",
            participant_logs_execute_url="http://participant-logs/execute",
            participant_logs_transport=httpx.ASGITransport(app=create_participant_logs_app()),
        )

    assert persistence.recorded_batches == [["fap.task.create"]]

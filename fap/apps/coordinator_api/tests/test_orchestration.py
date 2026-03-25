"""Tests for coordinator one-shot orchestration helpers."""

from __future__ import annotations

from collections.abc import Sequence

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from coordinator_api.service.orchestration import (
    NoExecutableParticipantsError,
    ParticipantIdentityMismatchError,
    ParticipantOrchestrationFailedError,
    orchestrate_run_summary_merge,
)
from coordinator_api.service.persistence import PersistedEventSummary
from coordinator_api.service.state import RunSnapshot
from coordinator_api.service.store import InMemoryRunStore
from fap_core.clocks import utc_now
from fap_core.enums import MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import (
    MessageEnvelope,
    SupportedMessage,
    TaskCreateMessage,
    TaskCreatePayload,
)
from participant_docs.main import create_app as create_participant_docs_app
from participant_kb.main import create_app as create_participant_kb_app
from participant_logs.main import create_app as create_participant_logs_app


class RecordingPersistenceService:
    """In-memory persistence stub for orchestration tests."""

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


def build_task_create_message(*, requested_capabilities: list[str]) -> TaskCreateMessage:
    """Return a valid task-create message for orchestration tests."""
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


@pytest.mark.anyio
async def test_all_participants_accept_execute_and_aggregate_succeeds() -> None:
    """Empty requested capabilities should let all participants execute and aggregate."""
    store = InMemoryRunStore()
    persistence = RecordingPersistenceService()
    create_message = build_task_create_message(requested_capabilities=[])
    store.record_task_create(create_message)

    result = await orchestrate_run_summary_merge(
        create_message.envelope.run_id,
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

    assert [entry.participant for entry in result.evaluations] == [
        "participant_docs",
        "participant_kb",
        "participant_logs",
    ]
    assert [entry.accepted for entry in result.evaluations] == [True, True, True]
    assert [entry.executed for entry in result.executions] == [True, True, True]
    assert result.aggregate_result.payload.participant_count == 3
    assert persistence.recorded_batches == [
        ["fap.task.accept"],
        ["fap.task.accept"],
        ["fap.task.accept"],
        ["fap.task.complete", "fap.policy.attest", "fap.aggregate.submit"],
        ["fap.task.complete", "fap.policy.attest", "fap.aggregate.submit"],
        ["fap.task.complete", "fap.policy.attest", "fap.aggregate.submit"],
        ["fap.aggregate.result"],
    ]


@pytest.mark.anyio
async def test_one_participant_rejects_and_other_executes_then_aggregation_succeeds() -> None:
    """One accepted participant should still produce a valid aggregate result."""
    store = InMemoryRunStore()
    persistence = RecordingPersistenceService()
    create_message = build_task_create_message(requested_capabilities=["docs.search"])
    store.record_task_create(create_message)

    result = await orchestrate_run_summary_merge(
        create_message.envelope.run_id,
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

    assert [entry.accepted for entry in result.evaluations] == [True, False, False]
    assert [entry.executed for entry in result.executions] == [True, False, False]
    assert result.aggregate_result.payload.participant_count == 1
    assert result.aggregate_result.payload.final_answer.startswith("[participant_docs]")


@pytest.mark.anyio
async def test_both_participants_reject_raises_no_executable_participants() -> None:
    """If all evaluations reject, orchestration should stop before aggregation."""
    store = InMemoryRunStore()
    persistence = RecordingPersistenceService()
    create_message = build_task_create_message(requested_capabilities=["docs.translate"])
    store.record_task_create(create_message)

    with pytest.raises(NoExecutableParticipantsError, match="No participants accepted execution"):
        await orchestrate_run_summary_merge(
            create_message.envelope.run_id,
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


@pytest.mark.anyio
async def test_participant_dispatch_failure_surfaces_as_orchestration_failure() -> None:
    """Participant dispatch errors should bubble as orchestration failures."""
    store = InMemoryRunStore()
    persistence = RecordingPersistenceService()
    create_message = build_task_create_message(requested_capabilities=[])
    store.record_task_create(create_message)

    with pytest.raises(
        ParticipantOrchestrationFailedError,
        match="participant_docs evaluation failed with status 503",
    ):
        await orchestrate_run_summary_merge(
            create_message.envelope.run_id,
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


@pytest.mark.anyio
async def test_orchestration_result_preserves_fixed_participant_ordering() -> None:
    """The orchestration result should always report docs, kb, then logs."""
    store = InMemoryRunStore()
    persistence = RecordingPersistenceService()
    create_message = build_task_create_message(requested_capabilities=[])
    store.record_task_create(create_message)

    result = await orchestrate_run_summary_merge(
        create_message.envelope.run_id,
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

    assert [entry.participant for entry in result.evaluations] == [
        "participant_docs",
        "participant_kb",
        "participant_logs",
    ]
    assert [entry.participant for entry in result.executions] == [
        "participant_docs",
        "participant_kb",
        "participant_logs",
    ]


@pytest.mark.anyio
async def test_identity_mismatch_surfaces_cleanly_from_orchestration() -> None:
    """Trusted participant identity mismatches should bubble out of orchestration."""
    store = InMemoryRunStore()
    persistence = RecordingPersistenceService()
    create_message = build_task_create_message(requested_capabilities=[])
    store.record_task_create(create_message)

    with pytest.raises(
        ParticipantIdentityMismatchError,
        match="expected sender_id/domain_id/recipient_id 'participant_docs'/'participant_docs'/'coordinator'",
    ):
        await orchestrate_run_summary_merge(
            create_message.envelope.run_id,
            store=store,
            persistence_service=persistence,
            participant_docs_evaluate_url="http://participant-docs/evaluate",
            participant_docs_execute_url="http://participant-docs/execute",
            participant_docs_transport=httpx.ASGITransport(app=create_identity_mismatch_docs_app()),
            participant_kb_evaluate_url="http://participant-kb/evaluate",
            participant_kb_execute_url="http://participant-kb/execute",
            participant_kb_transport=httpx.ASGITransport(app=create_participant_kb_app()),
            participant_logs_evaluate_url="http://participant-logs/evaluate",
            participant_logs_execute_url="http://participant-logs/execute",
            participant_logs_transport=httpx.ASGITransport(app=create_participant_logs_app()),
        )

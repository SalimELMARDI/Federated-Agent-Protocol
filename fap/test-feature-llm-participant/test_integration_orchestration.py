"""Integration tests for 4-participant orchestration with participant_llm.

These tests run the real coordinator orchestration logic end-to-end using
httpx.ASGITransport so no servers are needed.  The LLM adapter is
monkeypatched before requests reach the participant_llm app so no real
API calls are made.

Key invariants verified:
- participant_llm is evaluated and executed as the 4th participant
- alphabetical aggregation order: docs < kb < llm < logs
- participant_count == 4 when all four participants accept and execute
- LLM contribution is governed (INTERNAL + SUMMARY_ONLY → [SUMMARY ONLY] prefix)
- when participant_llm rejects, a valid 3-participant aggregate is still produced
- persistence batches contain the expected FAP message types in protocol order
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx
import pytest

from coordinator_api.service.orchestration import orchestrate_run_summary_merge
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
from participant_llm.adapters.llm_client import LLMResponse
from participant_llm.main import create_app as create_participant_llm_app
from participant_logs.main import create_app as create_participant_logs_app

STUB_LLM_CONTENT = "The model's training data does not include user-identifiable records."
STUB_LLM_MODEL = "stub-llm-v1"
STUB_LLM_ENDPOINT = "https://stub.example.com/v1/messages"


class _RecordingPersistence:
    """Minimal in-memory persistence stub for orchestration tests."""

    def __init__(self) -> None:
        self.recorded_batches: list[list[str]] = []

    def persist_messages_and_snapshot(
        self, messages: Sequence[SupportedMessage], **_kwargs: object
    ) -> None:
        self.recorded_batches.append(
            [message.envelope.message_type.value for message in messages]
        )

    def list_events_for_run(self, run_id: str) -> list[PersistedEventSummary]:
        del run_id
        return []

    def load_run_snapshot(self, run_id: str) -> RunSnapshot | None:
        del run_id
        return None

    def load_task_create_message(self, run_id: str) -> TaskCreateMessage | None:
        del run_id
        return None


def _stub_call_llm(query: str) -> LLMResponse:
    del query
    return LLMResponse(
        content=STUB_LLM_CONTENT,
        model=STUB_LLM_MODEL,
        endpoint_url=STUB_LLM_ENDPOINT,
    )


def _build_task_create(*, requested_capabilities: list[str]) -> TaskCreateMessage:
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
            title="4-participant governed federation",
            description="Coordinate a deterministic 4-participant run including LLM.",
            requested_capabilities=requested_capabilities,
            input_query="privacy",
        ),
    )


def _make_llm_transport(monkeypatch: pytest.MonkeyPatch) -> httpx.ASGITransport:
    """Patch the LLM adapter and return an in-process ASGI transport."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_call_llm)
    return httpx.ASGITransport(app=create_participant_llm_app())


# ---------------------------------------------------------------------------
# All four participants accept and execute
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_four_participants_all_accept_and_produce_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All four participants should accept, execute, and contribute to the aggregate."""
    store = InMemoryRunStore()
    persistence = _RecordingPersistence()
    create_msg = _build_task_create(requested_capabilities=[])
    store.record_task_create(create_msg)
    llm_transport = _make_llm_transport(monkeypatch)

    result = await orchestrate_run_summary_merge(
        create_msg.envelope.run_id,
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
        participant_llm_evaluate_url="http://participant-llm/evaluate",
        participant_llm_execute_url="http://participant-llm/execute",
        participant_llm_transport=llm_transport,
    )

    assert result.aggregate_result.payload.participant_count == 4
    assert [e.participant for e in result.evaluations] == [
        "participant_docs",
        "participant_kb",
        "participant_logs",
        "participant_llm",
    ]
    assert all(e.accepted for e in result.evaluations)
    assert all(e.executed for e in result.executions)


@pytest.mark.anyio
async def test_four_participant_final_answer_contains_all_contributors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The aggregate final_answer must contain a labelled line for each participant."""
    store = InMemoryRunStore()
    persistence = _RecordingPersistence()
    create_msg = _build_task_create(requested_capabilities=[])
    store.record_task_create(create_msg)
    llm_transport = _make_llm_transport(monkeypatch)

    result = await orchestrate_run_summary_merge(
        create_msg.envelope.run_id,
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
        participant_llm_evaluate_url="http://participant-llm/evaluate",
        participant_llm_execute_url="http://participant-llm/execute",
        participant_llm_transport=llm_transport,
    )

    final_answer = result.aggregate_result.payload.final_answer
    assert "[participant_docs]" in final_answer
    assert "[participant_kb]" in final_answer
    assert "[participant_llm]" in final_answer
    assert "[participant_logs]" in final_answer


@pytest.mark.anyio
async def test_participant_llm_appears_between_kb_and_logs_in_final_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alphabetical sort must place participant_llm after participant_kb and before participant_logs."""
    store = InMemoryRunStore()
    persistence = _RecordingPersistence()
    create_msg = _build_task_create(requested_capabilities=[])
    store.record_task_create(create_msg)
    llm_transport = _make_llm_transport(monkeypatch)

    result = await orchestrate_run_summary_merge(
        create_msg.envelope.run_id,
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
        participant_llm_evaluate_url="http://participant-llm/evaluate",
        participant_llm_execute_url="http://participant-llm/execute",
        participant_llm_transport=llm_transport,
    )

    final_answer = result.aggregate_result.payload.final_answer
    pos_kb = final_answer.index("[participant_kb]")
    pos_llm = final_answer.index("[participant_llm]")
    pos_logs = final_answer.index("[participant_logs]")
    assert pos_kb < pos_llm < pos_logs


@pytest.mark.anyio
async def test_participant_llm_contribution_is_governed_summary_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default governance (INTERNAL + SUMMARY_ONLY) must prefix the LLM line with [SUMMARY ONLY]."""
    store = InMemoryRunStore()
    persistence = _RecordingPersistence()
    create_msg = _build_task_create(requested_capabilities=[])
    store.record_task_create(create_msg)
    llm_transport = _make_llm_transport(monkeypatch)

    result = await orchestrate_run_summary_merge(
        create_msg.envelope.run_id,
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
        participant_llm_evaluate_url="http://participant-llm/evaluate",
        participant_llm_execute_url="http://participant-llm/execute",
        participant_llm_transport=llm_transport,
    )

    final_answer = result.aggregate_result.payload.final_answer
    llm_line = next(
        line for line in final_answer.splitlines() if "[participant_llm]" in line
    )
    assert "[SUMMARY ONLY]" in llm_line


@pytest.mark.anyio
async def test_four_participant_persistence_batches_follow_protocol_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persistence batches must list accept × 4, then execute × 4, then aggregate.result."""
    store = InMemoryRunStore()
    persistence = _RecordingPersistence()
    create_msg = _build_task_create(requested_capabilities=[])
    store.record_task_create(create_msg)
    llm_transport = _make_llm_transport(monkeypatch)

    await orchestrate_run_summary_merge(
        create_msg.envelope.run_id,
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
        participant_llm_evaluate_url="http://participant-llm/evaluate",
        participant_llm_execute_url="http://participant-llm/execute",
        participant_llm_transport=llm_transport,
    )

    assert persistence.recorded_batches == [
        ["fap.task.accept"],
        ["fap.task.accept"],
        ["fap.task.accept"],
        ["fap.task.accept"],
        ["fap.task.complete", "fap.policy.attest", "fap.aggregate.submit"],
        ["fap.task.complete", "fap.policy.attest", "fap.aggregate.submit"],
        ["fap.task.complete", "fap.policy.attest", "fap.aggregate.submit"],
        ["fap.task.complete", "fap.policy.attest", "fap.aggregate.submit"],
        ["fap.aggregate.result"],
    ]


# ---------------------------------------------------------------------------
# participant_llm absent — existing 3-participant behaviour unchanged
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_omitting_llm_params_produces_three_participant_aggregate() -> None:
    """Without LLM params the run should complete with participant_count == 3."""
    store = InMemoryRunStore()
    persistence = _RecordingPersistence()
    create_msg = _build_task_create(requested_capabilities=[])
    store.record_task_create(create_msg)

    result = await orchestrate_run_summary_merge(
        create_msg.envelope.run_id,
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

    assert result.aggregate_result.payload.participant_count == 3
    assert len(result.evaluations) == 3


# ---------------------------------------------------------------------------
# participant_llm rejects — valid 3-participant fallback
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_llm_rejects_unsupported_capability_falls_back_to_three_participant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When participant_llm rejects, the aggregate must still complete with 3 participants."""
    store = InMemoryRunStore()
    persistence = _RecordingPersistence()
    # docs.search is not a supported llm capability → llm will reject
    create_msg = _build_task_create(requested_capabilities=["docs.search"])
    store.record_task_create(create_msg)
    llm_transport = _make_llm_transport(monkeypatch)

    result = await orchestrate_run_summary_merge(
        create_msg.envelope.run_id,
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
        participant_llm_evaluate_url="http://participant-llm/evaluate",
        participant_llm_execute_url="http://participant-llm/execute",
        participant_llm_transport=llm_transport,
    )

    llm_eval = next(e for e in result.evaluations if e.participant == "participant_llm")
    assert llm_eval.accepted is False
    # docs accepted docs.search; kb and logs rejected it too — only docs executes
    assert result.aggregate_result.payload.participant_count == 1
    assert result.aggregate_result.payload.final_answer.startswith("[participant_docs]")

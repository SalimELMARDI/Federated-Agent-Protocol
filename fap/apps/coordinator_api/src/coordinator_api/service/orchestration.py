"""One-shot orchestration helpers for coordinator runtime flows."""

from __future__ import annotations

from collections.abc import Sequence

import httpx
from pydantic import BaseModel, ConfigDict

from coordinator_api.service.aggregation import (
    NoCompletedParticipantsError,
    aggregate_run_summary_merge,
)
from coordinator_api.service.dispatch import (
    InvalidParticipantExecutionResponseError,
    InvalidParticipantResponseError,
    ParticipantExecutionDispatchResult,
    ParticipantExecutionFailedError,
    ParticipantEvaluationFailedError,
    ParticipantIdentityMismatchError,
    RunNotFoundError,
    dispatch_run_to_participant_kb,
    dispatch_run_to_participant_kb_execute,
    dispatch_run_to_participant_logs,
    dispatch_run_to_participant_logs_execute,
    dispatch_run_to_participant_docs,
    dispatch_run_to_participant_docs_execute,
)
from coordinator_api.service.persistence import PersistenceService
from coordinator_api.service.store import CoordinatorStore, InMemoryRunStore
from fap_core.messages import (
    AggregateResultMessage,
    SupportedMessage,
    TaskAcceptMessage,
    TaskRejectMessage,
)


class ParticipantEvaluationRecord(BaseModel):
    """Stable summary of one participant evaluation step."""

    model_config = ConfigDict(extra="forbid")

    participant: str
    message_type: str
    accepted: bool


class ParticipantExecutionRecord(BaseModel):
    """Stable summary of one participant execution step."""

    model_config = ConfigDict(extra="forbid")

    participant: str
    executed: bool
    message_type: str


class OrchestrationResult(BaseModel):
    """Structured result returned by one-shot coordinator orchestration."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    evaluations: list[ParticipantEvaluationRecord]
    executions: list[ParticipantExecutionRecord]
    aggregate_result: AggregateResultMessage


class NoExecutableParticipantsError(Exception):
    """Raised when all participants reject a run during evaluation."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"No participants accepted execution for run: {run_id!r}")


class ParticipantOrchestrationFailedError(Exception):
    """Raised when a participant evaluate/execute step fails during orchestration."""


async def orchestrate_run_summary_merge(
    run_id: str,
    *,
    store: CoordinatorStore,
    persistence_service: PersistenceService,
    participant_docs_evaluate_url: str,
    participant_docs_execute_url: str,
    participant_docs_transport: httpx.AsyncBaseTransport | None = None,
    participant_kb_evaluate_url: str,
    participant_kb_execute_url: str,
    participant_kb_transport: httpx.AsyncBaseTransport | None = None,
    participant_logs_evaluate_url: str,
    participant_logs_execute_url: str,
    participant_logs_transport: httpx.AsyncBaseTransport | None = None,
) -> OrchestrationResult:
    """Run a full federated evaluate -> execute -> aggregate flow in fixed participant order."""
    if store.get_run(run_id) is None:
        raise RunNotFoundError(run_id)

    evaluations: list[ParticipantEvaluationRecord] = []
    executions: list[ParticipantExecutionRecord] = []

    docs_decision = await _evaluate_participant_docs(
        run_id,
        store=store,
        persistence_service=persistence_service,
        evaluate_url=participant_docs_evaluate_url,
        transport=participant_docs_transport,
    )
    evaluations.append(
        ParticipantEvaluationRecord(
            participant="participant_docs",
            message_type=docs_decision.envelope.message_type.value,
            accepted=isinstance(docs_decision, TaskAcceptMessage),
        )
    )

    kb_decision = await _evaluate_participant_kb(
        run_id,
        store=store,
        persistence_service=persistence_service,
        evaluate_url=participant_kb_evaluate_url,
        transport=participant_kb_transport,
    )
    evaluations.append(
        ParticipantEvaluationRecord(
            participant="participant_kb",
            message_type=kb_decision.envelope.message_type.value,
            accepted=isinstance(kb_decision, TaskAcceptMessage),
        )
    )
    logs_decision = await _evaluate_participant_logs(
        run_id,
        store=store,
        persistence_service=persistence_service,
        evaluate_url=participant_logs_evaluate_url,
        transport=participant_logs_transport,
    )
    evaluations.append(
        ParticipantEvaluationRecord(
            participant="participant_logs",
            message_type=logs_decision.envelope.message_type.value,
            accepted=isinstance(logs_decision, TaskAcceptMessage),
        )
    )

    any_executed = False
    if isinstance(docs_decision, TaskAcceptMessage):
        await _execute_participant_docs(
            run_id,
            store=store,
            persistence_service=persistence_service,
            execute_url=participant_docs_execute_url,
            transport=participant_docs_transport,
        )
        executions.append(
            ParticipantExecutionRecord(
                participant="participant_docs",
                executed=True,
                message_type="fap.task.complete",
            )
        )
        any_executed = True
    else:
        executions.append(
            ParticipantExecutionRecord(
                participant="participant_docs",
                executed=False,
                message_type="skipped",
            )
        )

    if isinstance(kb_decision, TaskAcceptMessage):
        await _execute_participant_kb(
            run_id,
            store=store,
            persistence_service=persistence_service,
            execute_url=participant_kb_execute_url,
            transport=participant_kb_transport,
        )
        executions.append(
            ParticipantExecutionRecord(
                participant="participant_kb",
                executed=True,
                message_type="fap.task.complete",
            )
        )
        any_executed = True
    else:
        executions.append(
            ParticipantExecutionRecord(
                participant="participant_kb",
                executed=False,
                message_type="skipped",
            )
        )

    if isinstance(logs_decision, TaskAcceptMessage):
        await _execute_participant_logs(
            run_id,
            store=store,
            persistence_service=persistence_service,
            execute_url=participant_logs_execute_url,
            transport=participant_logs_transport,
        )
        executions.append(
            ParticipantExecutionRecord(
                participant="participant_logs",
                executed=True,
                message_type="fap.task.complete",
            )
        )
        any_executed = True
    else:
        executions.append(
            ParticipantExecutionRecord(
                participant="participant_logs",
                executed=False,
                message_type="skipped",
            )
        )

    if not any_executed:
        raise NoExecutableParticipantsError(run_id)

    try:
        aggregate_result = aggregate_run_summary_merge(run_id, store=store)
        store.record_aggregate_result(aggregate_result)
    except NoCompletedParticipantsError as exc:
        raise ParticipantOrchestrationFailedError(str(exc)) from exc

    _persist_updated_run_if_needed(
        run_id,
        store=store,
        persistence_service=persistence_service,
        messages=[aggregate_result],
    )

    return OrchestrationResult(
        run_id=run_id,
        evaluations=evaluations,
        executions=executions,
        aggregate_result=aggregate_result,
    )


async def _evaluate_participant_docs(
    run_id: str,
    *,
    store: CoordinatorStore,
    persistence_service: PersistenceService,
    evaluate_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> TaskAcceptMessage | TaskRejectMessage:
    """Evaluate participant_docs and persist the returned decision."""
    try:
        decision = await dispatch_run_to_participant_docs(
            run_id,
            store=store,
            evaluate_url=evaluate_url,
            transport=transport,
        )
    except (
        ParticipantEvaluationFailedError,
        InvalidParticipantResponseError,
        ParticipantExecutionFailedError,
        InvalidParticipantExecutionResponseError,
    ) as exc:
        raise ParticipantOrchestrationFailedError(str(exc)) from exc
    except ParticipantIdentityMismatchError:
        raise

    _persist_updated_run(run_id, store=store, persistence_service=persistence_service, messages=[decision])
    return decision


async def _evaluate_participant_kb(
    run_id: str,
    *,
    store: CoordinatorStore,
    persistence_service: PersistenceService,
    evaluate_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> TaskAcceptMessage | TaskRejectMessage:
    """Evaluate participant_kb and persist the returned decision."""
    try:
        decision = await dispatch_run_to_participant_kb(
            run_id,
            store=store,
            evaluate_url=evaluate_url,
            transport=transport,
        )
    except (
        ParticipantEvaluationFailedError,
        InvalidParticipantResponseError,
        ParticipantExecutionFailedError,
        InvalidParticipantExecutionResponseError,
    ) as exc:
        raise ParticipantOrchestrationFailedError(str(exc)) from exc
    except ParticipantIdentityMismatchError:
        raise

    _persist_updated_run(run_id, store=store, persistence_service=persistence_service, messages=[decision])
    return decision


async def _evaluate_participant_logs(
    run_id: str,
    *,
    store: CoordinatorStore,
    persistence_service: PersistenceService,
    evaluate_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> TaskAcceptMessage | TaskRejectMessage:
    """Evaluate participant_logs and persist the returned decision."""
    try:
        decision = await dispatch_run_to_participant_logs(
            run_id,
            store=store,
            evaluate_url=evaluate_url,
            transport=transport,
        )
    except (
        ParticipantEvaluationFailedError,
        InvalidParticipantResponseError,
        ParticipantExecutionFailedError,
        InvalidParticipantExecutionResponseError,
    ) as exc:
        raise ParticipantOrchestrationFailedError(str(exc)) from exc
    except ParticipantIdentityMismatchError:
        raise

    _persist_updated_run(run_id, store=store, persistence_service=persistence_service, messages=[decision])
    return decision


async def _execute_participant_docs(
    run_id: str,
    *,
    store: CoordinatorStore,
    persistence_service: PersistenceService,
    execute_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ParticipantExecutionDispatchResult:
    """Execute participant_docs and persist the governed outputs."""
    try:
        result = await dispatch_run_to_participant_docs_execute(
            run_id,
            store=store,
            execute_url=execute_url,
            transport=transport,
        )
    except (
        ParticipantEvaluationFailedError,
        InvalidParticipantResponseError,
        ParticipantExecutionFailedError,
        InvalidParticipantExecutionResponseError,
    ) as exc:
        raise ParticipantOrchestrationFailedError(str(exc)) from exc
    except ParticipantIdentityMismatchError:
        raise

    _persist_updated_run(
        run_id,
        store=store,
        persistence_service=persistence_service,
        messages=[
            result.task_complete_message,
            result.policy_attest_message,
            result.aggregate_submit_message,
        ],
    )
    return result


async def _execute_participant_kb(
    run_id: str,
    *,
    store: CoordinatorStore,
    persistence_service: PersistenceService,
    execute_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ParticipantExecutionDispatchResult:
    """Execute participant_kb and persist the governed outputs."""
    try:
        result = await dispatch_run_to_participant_kb_execute(
            run_id,
            store=store,
            execute_url=execute_url,
            transport=transport,
        )
    except (
        ParticipantEvaluationFailedError,
        InvalidParticipantResponseError,
        ParticipantExecutionFailedError,
        InvalidParticipantExecutionResponseError,
    ) as exc:
        raise ParticipantOrchestrationFailedError(str(exc)) from exc
    except ParticipantIdentityMismatchError:
        raise

    _persist_updated_run(
        run_id,
        store=store,
        persistence_service=persistence_service,
        messages=[
            result.task_complete_message,
            result.policy_attest_message,
            result.aggregate_submit_message,
        ],
    )
    return result


async def _execute_participant_logs(
    run_id: str,
    *,
    store: CoordinatorStore,
    persistence_service: PersistenceService,
    execute_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ParticipantExecutionDispatchResult:
    """Execute participant_logs and persist the governed outputs."""
    try:
        result = await dispatch_run_to_participant_logs_execute(
            run_id,
            store=store,
            execute_url=execute_url,
            transport=transport,
        )
    except (
        ParticipantEvaluationFailedError,
        InvalidParticipantResponseError,
        ParticipantExecutionFailedError,
        InvalidParticipantExecutionResponseError,
    ) as exc:
        raise ParticipantOrchestrationFailedError(str(exc)) from exc
    except ParticipantIdentityMismatchError:
        raise

    _persist_updated_run(
        run_id,
        store=store,
        persistence_service=persistence_service,
        messages=[
            result.task_complete_message,
            result.policy_attest_message,
            result.aggregate_submit_message,
        ],
    )
    return result


def _persist_updated_run(
    run_id: str,
    *,
    store: CoordinatorStore,
    persistence_service: PersistenceService,
    messages: Sequence[SupportedMessage],
) -> None:
    """Persist runtime messages plus the updated run snapshot for legacy in-memory flows."""
    _persist_updated_run_if_needed(
        run_id,
        store=store,
        persistence_service=persistence_service,
        messages=messages,
    )


def _persist_updated_run_if_needed(
    run_id: str,
    *,
    store: CoordinatorStore,
    persistence_service: PersistenceService,
    messages: Sequence[SupportedMessage],
) -> None:
    """Persist runtime messages only when using the compatibility in-memory store."""
    if not isinstance(store, InMemoryRunStore):
        return

    snapshot = store.get_run(run_id)
    if snapshot is None:
        raise RunNotFoundError(run_id)
    persistence_service.persist_messages_and_snapshot(messages, snapshot=snapshot)

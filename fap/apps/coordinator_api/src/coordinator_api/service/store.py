"""Coordinator store abstractions and run-state transition helpers."""

from __future__ import annotations

from threading import Lock
from typing import Protocol, runtime_checkable

from coordinator_api.service.persistence import PersistedEventSummary, PersistenceService
from coordinator_api.service.state import (
    AggregateResultRecord,
    AggregateSubmissionRecord,
    CompletedParticipant,
    PolicyAttestationRecord,
    RejectedParticipant,
    RunSnapshot,
)
from fap_core.enums import RunStatus
from fap_core.messages import (
    AggregateResultMessage,
    AggregateSubmitMessage,
    PolicyAttestMessage,
    SupportedMessage,
    TaskAcceptMessage,
    TaskCompleteMessage,
    TaskCreateMessage,
    TaskRejectMessage,
)


class CoordinatorStateError(Exception):
    """Base error for coordinator run-state operations."""


class RunAlreadyExistsError(CoordinatorStateError):
    """Raised when a run is created more than once."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"Run already exists: {run_id!r}")


class UnknownRunError(CoordinatorStateError):
    """Raised when a decision message references an unknown run."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"Unknown run: {run_id!r}")


@runtime_checkable
class CoordinatorStore(Protocol):
    """Protocol for coordinator runtime state stores."""

    def record_message(self, message: SupportedMessage) -> RunSnapshot | None:
        """Record a tracked message and return the updated run snapshot when applicable."""

    def record_task_create(self, message: TaskCreateMessage) -> RunSnapshot:
        """Initialize a new run from a task-create message."""

    def record_task_accept(self, message: TaskAcceptMessage) -> RunSnapshot:
        """Record a participant acceptance for an existing run."""

    def record_task_reject(self, message: TaskRejectMessage) -> RunSnapshot:
        """Record a participant rejection for an existing run."""

    def record_task_complete(self, message: TaskCompleteMessage) -> RunSnapshot:
        """Record a participant completion for an existing run."""

    def record_policy_attest(self, message: PolicyAttestMessage) -> RunSnapshot:
        """Record a policy attestation for an existing run."""

    def record_aggregate_submit(self, message: AggregateSubmitMessage) -> RunSnapshot:
        """Record an aggregate submission for an existing run."""

    def record_aggregate_result(self, message: AggregateResultMessage) -> RunSnapshot:
        """Record an aggregate result for an existing run."""

    def get_run(self, run_id: str) -> RunSnapshot | None:
        """Return the current run snapshot if it exists."""

    def get_task_create_message(self, run_id: str) -> TaskCreateMessage | None:
        """Return the canonical stored task-create message for a run if present."""

    def list_events_for_run(self, run_id: str) -> list[PersistedEventSummary]:
        """Return persisted event summaries for a run when available."""


class InMemoryRunStore:
    """Small in-memory coordinator store for isolated tests and compatibility flows."""

    def __init__(self) -> None:
        self._runs: dict[str, RunSnapshot] = {}
        self._task_create_messages: dict[str, TaskCreateMessage] = {}
        self._lock = Lock()

    def reset(self) -> None:
        """Clear all in-memory run state."""
        with self._lock:
            self._runs.clear()
            self._task_create_messages.clear()

    def record_message(self, message: SupportedMessage) -> RunSnapshot | None:
        """Record tracked protocol messages and ignore currently untracked kinds."""
        if isinstance(message, TaskCreateMessage):
            return self.record_task_create(message)
        if isinstance(message, TaskAcceptMessage):
            return self.record_task_accept(message)
        if isinstance(message, TaskRejectMessage):
            return self.record_task_reject(message)
        if isinstance(message, TaskCompleteMessage):
            return self.record_task_complete(message)
        if isinstance(message, PolicyAttestMessage):
            return self.record_policy_attest(message)
        if isinstance(message, AggregateSubmitMessage):
            return self.record_aggregate_submit(message)
        if isinstance(message, AggregateResultMessage):
            return self.record_aggregate_result(message)
        return None

    def record_task_create(self, message: TaskCreateMessage) -> RunSnapshot:
        """Initialize a new run from a task-create message."""
        with self._lock:
            run_id = message.envelope.run_id
            if run_id in self._runs:
                raise RunAlreadyExistsError(run_id)

            snapshot = _initialize_run_snapshot(message)
            self._runs[run_id] = snapshot
            self._task_create_messages[run_id] = message.model_copy(deep=True)
            return snapshot.model_copy(deep=True)

    def record_task_accept(self, message: TaskAcceptMessage) -> RunSnapshot:
        """Record a participant acceptance for an existing run."""
        with self._lock:
            snapshot = self._require_run(message.envelope.run_id)
            _apply_task_accept(snapshot, message)
            return snapshot.model_copy(deep=True)

    def record_task_reject(self, message: TaskRejectMessage) -> RunSnapshot:
        """Record a participant rejection for an existing run."""
        with self._lock:
            snapshot = self._require_run(message.envelope.run_id)
            _apply_task_reject(snapshot, message)
            return snapshot.model_copy(deep=True)

    def record_task_complete(self, message: TaskCompleteMessage) -> RunSnapshot:
        """Record a participant completion for an existing run."""
        with self._lock:
            snapshot = self._require_run(message.envelope.run_id)
            _apply_task_complete(snapshot, message)
            return snapshot.model_copy(deep=True)

    def record_policy_attest(self, message: PolicyAttestMessage) -> RunSnapshot:
        """Record a policy attestation for an existing run."""
        with self._lock:
            snapshot = self._require_run(message.envelope.run_id)
            _apply_policy_attest(snapshot, message)
            return snapshot.model_copy(deep=True)

    def record_aggregate_submit(self, message: AggregateSubmitMessage) -> RunSnapshot:
        """Record an aggregate submission for an existing run."""
        with self._lock:
            snapshot = self._require_run(message.envelope.run_id)
            _apply_aggregate_submit(snapshot, message)
            return snapshot.model_copy(deep=True)

    def record_aggregate_result(self, message: AggregateResultMessage) -> RunSnapshot:
        """Record an aggregate result for an existing run."""
        with self._lock:
            snapshot = self._require_run(message.envelope.run_id)
            _apply_aggregate_result(snapshot, message)
            return snapshot.model_copy(deep=True)

    def get_run(self, run_id: str) -> RunSnapshot | None:
        """Return a run snapshot if present."""
        with self._lock:
            snapshot = self._runs.get(run_id)
            if snapshot is None:
                return None
            return snapshot.model_copy(deep=True)

    def get_task_create_message(self, run_id: str) -> TaskCreateMessage | None:
        """Return the stored original task-create message for a run if present."""
        with self._lock:
            message = self._task_create_messages.get(run_id)
            if message is None:
                return None
            return message.model_copy(deep=True)

    def list_events_for_run(self, run_id: str) -> list[PersistedEventSummary]:
        """In-memory compatibility store does not persist events."""
        del run_id
        return []

    def _require_run(self, run_id: str) -> RunSnapshot:
        """Return a tracked run or raise an unknown-run error."""
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise UnknownRunError(run_id) from exc


class DatabaseBackedRunStore:
    """DB-first coordinator store backed by durable protocol events and run snapshots."""

    def __init__(self, persistence_service: PersistenceService) -> None:
        self._persistence_service = persistence_service

    def record_message(self, message: SupportedMessage) -> RunSnapshot | None:
        """Record a tracked message and persist it to the database-backed runtime state."""
        if isinstance(message, TaskCreateMessage):
            return self.record_task_create(message)
        if isinstance(message, TaskAcceptMessage):
            return self.record_task_accept(message)
        if isinstance(message, TaskRejectMessage):
            return self.record_task_reject(message)
        if isinstance(message, TaskCompleteMessage):
            return self.record_task_complete(message)
        if isinstance(message, PolicyAttestMessage):
            return self.record_policy_attest(message)
        if isinstance(message, AggregateSubmitMessage):
            return self.record_aggregate_submit(message)
        if isinstance(message, AggregateResultMessage):
            return self.record_aggregate_result(message)

        self._persistence_service.persist_messages_and_snapshot([message], snapshot=None)
        return None

    def record_task_create(self, message: TaskCreateMessage) -> RunSnapshot:
        """Initialize a new durable run from a task-create message."""
        run_id = message.envelope.run_id
        if self.get_run(run_id) is not None:
            raise RunAlreadyExistsError(run_id)

        snapshot = _initialize_run_snapshot(message)
        self._persistence_service.persist_messages_and_snapshot([message], snapshot=snapshot)
        return snapshot

    def record_task_accept(self, message: TaskAcceptMessage) -> RunSnapshot:
        """Record a participant acceptance in durable runtime state."""
        snapshot = self._require_run(message.envelope.run_id)
        _apply_task_accept(snapshot, message)
        self._persistence_service.persist_messages_and_snapshot([message], snapshot=snapshot)
        return snapshot

    def record_task_reject(self, message: TaskRejectMessage) -> RunSnapshot:
        """Record a participant rejection in durable runtime state."""
        snapshot = self._require_run(message.envelope.run_id)
        _apply_task_reject(snapshot, message)
        self._persistence_service.persist_messages_and_snapshot([message], snapshot=snapshot)
        return snapshot

    def record_task_complete(self, message: TaskCompleteMessage) -> RunSnapshot:
        """Record a participant completion in durable runtime state."""
        snapshot = self._require_run(message.envelope.run_id)
        _apply_task_complete(snapshot, message)
        self._persistence_service.persist_messages_and_snapshot([message], snapshot=snapshot)
        return snapshot

    def record_policy_attest(self, message: PolicyAttestMessage) -> RunSnapshot:
        """Record a policy attestation in durable runtime state."""
        snapshot = self._require_run(message.envelope.run_id)
        _apply_policy_attest(snapshot, message)
        self._persistence_service.persist_messages_and_snapshot([message], snapshot=snapshot)
        return snapshot

    def record_aggregate_submit(self, message: AggregateSubmitMessage) -> RunSnapshot:
        """Record an aggregate submission in durable runtime state."""
        snapshot = self._require_run(message.envelope.run_id)
        _apply_aggregate_submit(snapshot, message)
        self._persistence_service.persist_messages_and_snapshot([message], snapshot=snapshot)
        return snapshot

    def record_aggregate_result(self, message: AggregateResultMessage) -> RunSnapshot:
        """Record an aggregate result in durable runtime state."""
        snapshot = self._require_run(message.envelope.run_id)
        _apply_aggregate_result(snapshot, message)
        self._persistence_service.persist_messages_and_snapshot([message], snapshot=snapshot)
        return snapshot

    def get_run(self, run_id: str) -> RunSnapshot | None:
        """Return the latest durable snapshot for a run if present."""
        return self._persistence_service.load_run_snapshot(run_id)

    def get_task_create_message(self, run_id: str) -> TaskCreateMessage | None:
        """Return the original canonical task-create message for a run if present."""
        return self._persistence_service.load_task_create_message(run_id)

    def list_events_for_run(self, run_id: str) -> list[PersistedEventSummary]:
        """Return persisted event summaries for a run."""
        return self._persistence_service.list_events_for_run(run_id)

    def _require_run(self, run_id: str) -> RunSnapshot:
        """Return the durable run snapshot or raise an unknown-run error."""
        snapshot = self.get_run(run_id)
        if snapshot is None:
            raise UnknownRunError(run_id)
        return snapshot


def _initialize_run_snapshot(message: TaskCreateMessage) -> RunSnapshot:
    """Build the initial run snapshot from a task-create message."""
    return RunSnapshot(
        run_id=message.envelope.run_id,
        task_id=message.envelope.task_id,
        status=RunStatus.CREATED,
        created_message_id=message.envelope.message_id,
        last_message_type=message.envelope.message_type.value,
        message_count=1,
    )


def _apply_task_accept(snapshot: RunSnapshot, message: TaskAcceptMessage) -> None:
    """Apply a task-accept message to a mutable run snapshot."""
    participant_id = message.payload.participant_id
    if participant_id not in snapshot.accepted_participants:
        snapshot.accepted_participants.append(participant_id)
    snapshot.status = RunStatus.DECISIONS_RECORDED
    snapshot.last_message_type = message.envelope.message_type.value
    snapshot.message_count += 1


def _apply_task_reject(snapshot: RunSnapshot, message: TaskRejectMessage) -> None:
    """Apply a task-reject message to a mutable run snapshot."""
    snapshot.rejected_participants.append(
        RejectedParticipant(
            participant_id=message.payload.participant_id,
            reason=message.payload.reason,
            retryable=message.payload.retryable,
        )
    )
    snapshot.status = RunStatus.DECISIONS_RECORDED
    snapshot.last_message_type = message.envelope.message_type.value
    snapshot.message_count += 1


def _apply_task_complete(snapshot: RunSnapshot, message: TaskCompleteMessage) -> None:
    """Apply a task-complete message to a mutable run snapshot."""
    snapshot.completed_participants.append(
        CompletedParticipant(
            participant_id=message.payload.participant_id,
            status=message.payload.status,
            summary=message.payload.summary,
            message_id=message.envelope.message_id,
            source_refs=[source_ref.model_copy(deep=True) for source_ref in message.payload.source_refs],
        )
    )
    snapshot.status = RunStatus.COMPLETED_RECORDED
    snapshot.last_message_type = message.envelope.message_type.value
    snapshot.message_count += 1


def _apply_policy_attest(snapshot: RunSnapshot, message: PolicyAttestMessage) -> None:
    """Apply a policy-attest message to a mutable run snapshot."""
    snapshot.policy_attestations.append(
        PolicyAttestationRecord(
            participant_id=message.payload.participant_id,
            policy_ref=message.payload.policy_ref,
            original_privacy_class=message.payload.original_privacy_class,
            applied_sharing_mode=message.payload.applied_sharing_mode,
            transform_type=message.payload.transform_type,
            message_id=message.envelope.message_id,
        )
    )
    snapshot.last_message_type = message.envelope.message_type.value
    snapshot.message_count += 1


def _apply_aggregate_submit(snapshot: RunSnapshot, message: AggregateSubmitMessage) -> None:
    """Apply an aggregate-submit message to a mutable run snapshot."""
    snapshot.aggregate_submissions.append(
        AggregateSubmissionRecord(
            participant_id=message.payload.participant_id,
            contribution_type=message.payload.contribution_type,
            summary=message.payload.summary,
            vote=message.payload.vote,
            confidence=message.payload.confidence,
            provenance_ref=message.payload.provenance_ref,
            source_refs=[source_ref.model_copy(deep=True) for source_ref in message.payload.source_refs],
            message_id=message.envelope.message_id,
        )
    )
    snapshot.last_message_type = message.envelope.message_type.value
    snapshot.message_count += 1


def _apply_aggregate_result(snapshot: RunSnapshot, message: AggregateResultMessage) -> None:
    """Apply an aggregate-result message to a mutable run snapshot."""
    snapshot.aggregate_results.append(
        AggregateResultRecord(
            aggregation_mode=message.payload.aggregation_mode,
            final_answer=message.payload.final_answer,
            participant_count=message.payload.participant_count,
            provenance_refs=list(message.payload.provenance_refs),
            source_refs=[source_ref.model_copy(deep=True) for source_ref in message.payload.source_refs],
            message_id=message.envelope.message_id,
        )
    )
    snapshot.status = RunStatus.AGGREGATED_RECORDED
    snapshot.last_message_type = message.envelope.message_type.value
    snapshot.message_count += 1


__all__ = [
    "CoordinatorStateError",
    "CoordinatorStore",
    "DatabaseBackedRunStore",
    "InMemoryRunStore",
    "RunAlreadyExistsError",
    "UnknownRunError",
]

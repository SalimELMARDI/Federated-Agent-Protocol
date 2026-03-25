"""Tests for the in-memory coordinator run store."""

from __future__ import annotations

import pytest

from coordinator_api.service.store import InMemoryRunStore, RunAlreadyExistsError, UnknownRunError
from fap_core.clocks import utc_now
from fap_core.enums import MessageType, RunStatus
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import (
    MessageEnvelope,
    TaskAcceptMessage,
    TaskAcceptPayload,
    TaskCreateMessage,
    TaskCreatePayload,
    TaskRejectMessage,
    TaskRejectPayload,
)


def build_create_message(*, run_id: str | None = None) -> TaskCreateMessage:
    """Return a valid task-create message for store tests."""
    shared_run_id = new_run_id() if run_id is None else run_id
    return TaskCreateMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_CREATE,
            task_id=new_task_id(),
            run_id=shared_run_id,
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id="participant_docs",
            domain_id="docs",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
        ),
        payload=TaskCreatePayload(
            title="Summarize notes",
            description="Create a redacted summary for coordinator review.",
            requested_capabilities=["docs.search"],
            input_query="Summarize the incident notes.",
        ),
    )


def build_accept_message(create_message: TaskCreateMessage, *, participant_id: str) -> TaskAcceptMessage:
    """Return a valid task-accept message derived from a task-create message."""
    return TaskAcceptMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_ACCEPT,
            task_id=create_message.envelope.task_id,
            run_id=create_message.envelope.run_id,
            message_id=new_message_id(),
            sender_id=participant_id,
            recipient_id="coordinator",
            domain_id=participant_id,
            trace_id=create_message.envelope.trace_id,
            timestamp=utc_now(),
        ),
        payload=TaskAcceptPayload(
            participant_id=participant_id,
            accepted_capabilities=["docs.search"],
        ),
    )


def build_reject_message(create_message: TaskCreateMessage, *, participant_id: str) -> TaskRejectMessage:
    """Return a valid task-reject message derived from a task-create message."""
    return TaskRejectMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_REJECT,
            task_id=create_message.envelope.task_id,
            run_id=create_message.envelope.run_id,
            message_id=new_message_id(),
            sender_id=participant_id,
            recipient_id="coordinator",
            domain_id=participant_id,
            trace_id=create_message.envelope.trace_id,
            timestamp=utc_now(),
        ),
        payload=TaskRejectPayload(
            participant_id=participant_id,
            reason="Unsupported capabilities requested: docs.translate",
            retryable=False,
        ),
    )


def test_task_create_initializes_a_run() -> None:
    """A task-create message should initialize the run snapshot."""
    store = InMemoryRunStore()
    message = build_create_message()

    snapshot = store.record_task_create(message)

    assert snapshot.run_id == message.envelope.run_id
    assert snapshot.task_id == message.envelope.task_id
    assert snapshot.status == RunStatus.CREATED
    assert snapshot.created_message_id == message.envelope.message_id
    assert snapshot.last_message_type == "fap.task.create"
    assert snapshot.message_count == 1


def test_duplicate_task_create_is_rejected() -> None:
    """The same run cannot be created twice."""
    store = InMemoryRunStore()
    message = build_create_message()
    store.record_task_create(message)

    with pytest.raises(RunAlreadyExistsError, match="Run already exists"):
        store.record_task_create(build_create_message(run_id=message.envelope.run_id))


def test_task_accept_updates_accepted_participants() -> None:
    """Task-accept messages should add accepted participants only once."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)

    store.record_task_accept(build_accept_message(create_message, participant_id="participant_docs"))
    snapshot = store.record_task_accept(
        build_accept_message(create_message, participant_id="participant_docs")
    )

    assert snapshot.accepted_participants == ["participant_docs"]


def test_task_reject_updates_rejected_participants() -> None:
    """Task-reject messages should append structured rejection entries."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)

    snapshot = store.record_task_reject(
        build_reject_message(create_message, participant_id="participant_docs")
    )

    assert [entry.model_dump(mode="json") for entry in snapshot.rejected_participants] == [
        {
            "participant_id": "participant_docs",
            "reason": "Unsupported capabilities requested: docs.translate",
            "retryable": False,
        }
    ]


def test_task_accept_for_unknown_run_is_rejected() -> None:
    """Task-accept messages require the run to exist first."""
    store = InMemoryRunStore()
    create_message = build_create_message()

    with pytest.raises(UnknownRunError, match="Unknown run"):
        store.record_task_accept(build_accept_message(create_message, participant_id="participant_docs"))


def test_task_reject_for_unknown_run_is_rejected() -> None:
    """Task-reject messages require the run to exist first."""
    store = InMemoryRunStore()
    create_message = build_create_message()

    with pytest.raises(UnknownRunError, match="Unknown run"):
        store.record_task_reject(build_reject_message(create_message, participant_id="participant_docs"))


def test_message_count_and_last_message_type_update_correctly() -> None:
    """Tracked messages should update the run snapshot counters and last type."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_message(create_message)
    store.record_message(build_accept_message(create_message, participant_id="participant_docs"))
    store.record_message(build_reject_message(create_message, participant_id="participant_logs"))

    stored = store.get_run(create_message.envelope.run_id)
    assert stored is not None
    assert stored.message_count == 3
    assert stored.last_message_type == "fap.task.reject"
    assert stored.status == RunStatus.DECISIONS_RECORDED

"""Tests for the DB-backed coordinator runtime store."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from coordinator_api.db import create_session_factory, create_sqlalchemy_engine, init_db
from coordinator_api.service.aggregation import aggregate_run_summary_merge
from coordinator_api.service.dispatch import (
    dispatch_run_to_participant_docs,
    dispatch_run_to_participant_docs_execute,
)
from coordinator_api.service.orchestration import orchestrate_run_summary_merge
from coordinator_api.service.persistence import CoordinatorPersistenceService
from coordinator_api.service.store import DatabaseBackedRunStore
from fap_core.clocks import utc_now
from fap_core.enums import MessageType, RunStatus
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import MessageEnvelope, TaskCreateMessage, TaskCreatePayload
from participant_docs.main import create_app as create_participant_docs_app
from participant_kb.main import create_app as create_participant_kb_app
from participant_logs.main import create_app as create_participant_logs_app


def sqlite_url(path: Path) -> str:
    """Return a SQLite URL for a temporary database file."""
    return f"sqlite:///{path.as_posix()}"


def build_persistence_service(database_path: Path) -> CoordinatorPersistenceService:
    """Create a persistence service backed by a temporary SQLite database."""
    engine = create_sqlalchemy_engine(sqlite_url(database_path))
    init_db(engine)
    return CoordinatorPersistenceService(create_session_factory(engine))


def build_task_create_message(*, requested_capabilities: list[str]) -> TaskCreateMessage:
    """Return a valid task-create message for DB-backed store tests."""
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
            title="Query federated sources",
            description="Coordinate a governed run from persisted state.",
            requested_capabilities=requested_capabilities,
            input_query="privacy",
        ),
    )


def build_store(database_path: Path) -> DatabaseBackedRunStore:
    """Create a fresh DB-backed store against a shared SQLite database."""
    return DatabaseBackedRunStore(build_persistence_service(database_path))


def test_fresh_db_backed_store_instance_can_inspect_persisted_run(tmp_path: Path) -> None:
    """A fresh store instance should recover the durable snapshot and task-create message."""
    database_path = tmp_path / "coordinator.db"
    initial_store = build_store(database_path)
    create_message = build_task_create_message(requested_capabilities=["docs.search"])

    initial_store.record_task_create(create_message)

    recovered_store = build_store(database_path)
    snapshot = recovered_store.get_run(create_message.envelope.run_id)
    recovered_message = recovered_store.get_task_create_message(create_message.envelope.run_id)

    assert snapshot is not None
    assert snapshot.run_id == create_message.envelope.run_id
    assert snapshot.task_id == create_message.envelope.task_id
    assert snapshot.status == RunStatus.CREATED
    assert recovered_message is not None
    assert recovered_message.envelope.message_id == create_message.envelope.message_id
    assert recovered_message.payload.input_query == "privacy"


@pytest.mark.anyio
async def test_fresh_db_backed_store_instance_can_dispatch_evaluate_and_execute(
    tmp_path: Path,
) -> None:
    """A fresh store instance should continue evaluate and execute from persisted task-create state."""
    database_path = tmp_path / "coordinator.db"
    initial_store = build_store(database_path)
    create_message = build_task_create_message(requested_capabilities=["docs.search"])
    initial_store.record_task_create(create_message)

    evaluate_store = build_store(database_path)
    decision = await dispatch_run_to_participant_docs(
        create_message.envelope.run_id,
        store=evaluate_store,
        evaluate_url="http://participant-docs/evaluate",
        transport=httpx.ASGITransport(app=create_participant_docs_app()),
    )

    assert decision.envelope.message_type == MessageType.FAP_TASK_ACCEPT

    execute_store = build_store(database_path)
    result = await dispatch_run_to_participant_docs_execute(
        create_message.envelope.run_id,
        store=execute_store,
        execute_url="http://participant-docs/execute",
        transport=httpx.ASGITransport(app=create_participant_docs_app()),
    )

    snapshot = build_store(database_path).get_run(create_message.envelope.run_id)
    assert snapshot is not None
    assert snapshot.accepted_participants == ["participant_docs"]
    assert snapshot.completed_participants[0].participant_id == "participant_docs"
    assert snapshot.completed_participants[0].source_refs[0].source_id == "doc-002"
    assert snapshot.policy_attestations[0].participant_id == "participant_docs"
    assert snapshot.aggregate_submissions[0].participant_id == "participant_docs"
    assert snapshot.aggregate_submissions[0].source_refs[0].source_id == "doc-002"
    assert result.aggregate_submit_message.payload.provenance_ref == snapshot.policy_attestations[0].message_id


@pytest.mark.anyio
async def test_fresh_db_backed_store_instance_can_orchestrate_from_persisted_state(
    tmp_path: Path,
) -> None:
    """A fresh store instance should orchestrate a run using only persisted task-create state."""
    database_path = tmp_path / "coordinator.db"
    initial_store = build_store(database_path)
    create_message = build_task_create_message(requested_capabilities=[])
    initial_store.record_task_create(create_message)

    orchestrated = await orchestrate_run_summary_merge(
        create_message.envelope.run_id,
        store=build_store(database_path),
        persistence_service=build_persistence_service(database_path),
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

    recovered_snapshot = build_store(database_path).get_run(create_message.envelope.run_id)
    assert recovered_snapshot is not None
    assert orchestrated.aggregate_result.payload.participant_count == 3
    assert [source_ref.source_id for source_ref in orchestrated.aggregate_result.payload.source_refs] == [
        "doc-002",
        "kb-001",
        "log-002",
    ]
    assert recovered_snapshot.status == RunStatus.AGGREGATED_RECORDED
    assert recovered_snapshot.aggregate_results[0].message_id == orchestrated.aggregate_result.envelope.message_id


@pytest.mark.anyio
async def test_fresh_db_backed_store_instance_can_aggregate_from_persisted_submissions(
    tmp_path: Path,
) -> None:
    """A fresh store instance should aggregate from durable aggregate submissions only."""
    database_path = tmp_path / "coordinator.db"
    initial_store = build_store(database_path)
    create_message = build_task_create_message(requested_capabilities=["docs.search"])
    initial_store.record_task_create(create_message)

    await dispatch_run_to_participant_docs_execute(
        create_message.envelope.run_id,
        store=build_store(database_path),
        execute_url="http://participant-docs/execute",
        transport=httpx.ASGITransport(app=create_participant_docs_app()),
    )

    aggregate_store = build_store(database_path)
    aggregate_result = aggregate_run_summary_merge(
        create_message.envelope.run_id,
        store=aggregate_store,
    )
    aggregate_store.record_aggregate_result(aggregate_result)

    recovered_snapshot = build_store(database_path).get_run(create_message.envelope.run_id)
    assert recovered_snapshot is not None
    assert recovered_snapshot.aggregate_submissions[0].participant_id == "participant_docs"
    assert recovered_snapshot.aggregate_submissions[0].source_refs[0].source_id == "doc-002"
    assert recovered_snapshot.aggregate_results[0].message_id == aggregate_result.envelope.message_id
    assert recovered_snapshot.aggregate_results[0].participant_count == 1
    assert recovered_snapshot.aggregate_results[0].source_refs[0].source_id == "doc-002"
    assert recovered_snapshot.aggregate_results[0].provenance_refs == [
        recovered_snapshot.aggregate_submissions[0].provenance_ref
    ]

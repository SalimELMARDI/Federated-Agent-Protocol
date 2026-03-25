"""Tests for coordinator runtime persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path

from coordinator_api.db import ProtocolEvent, RunSnapshotRecord, create_session_factory, create_sqlalchemy_engine, init_db
from coordinator_api.service.persistence import CoordinatorPersistenceService
from coordinator_api.service.state import RunSnapshot
from coordinator_api.service.store import InMemoryRunStore
from fap_core.clocks import utc_now
from fap_core.enums import MessageType, RunStatus
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import MessageEnvelope, TaskCreateMessage, TaskCreatePayload


def sqlite_url(path: Path) -> str:
    """Return a SQLite URL for a temporary database file."""
    return f"sqlite:///{path.as_posix()}"


def build_task_create_message() -> TaskCreateMessage:
    """Return a valid task-create message for persistence tests."""
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
            title="Search local docs",
            description="Perform a deterministic local docs search.",
            requested_capabilities=["docs.search"],
            input_query="privacy",
        ),
    )


def build_service(database_path: Path) -> CoordinatorPersistenceService:
    """Create a persistence service backed by a temporary SQLite database."""
    engine = create_sqlalchemy_engine(sqlite_url(database_path))
    init_db(engine)
    return CoordinatorPersistenceService(create_session_factory(engine))


def test_persisting_canonical_message_creates_protocol_event_row(tmp_path: Path) -> None:
    """Persisting a message should create one durable protocol_events row."""
    database_path = tmp_path / "coordinator.db"
    service = build_service(database_path)
    message = build_task_create_message()

    service.persist_messages_and_snapshot([message])

    session_factory = create_session_factory(database_url=sqlite_url(database_path))
    with session_factory() as session:
        rows = session.query(ProtocolEvent).all()

    assert len(rows) == 1
    assert rows[0].message_id == message.envelope.message_id
    assert rows[0].message_type == "fap.task.create"


def test_upserting_run_snapshot_creates_and_then_updates_one_row(tmp_path: Path) -> None:
    """Persisting the same run snapshot twice should update a single durable row."""
    database_path = tmp_path / "coordinator.db"
    service = build_service(database_path)
    snapshot = RunSnapshot(
        run_id=new_run_id(),
        task_id=new_task_id(),
        status=RunStatus.CREATED,
        created_message_id=new_message_id(),
        last_message_type="fap.task.create",
        message_count=1,
    )

    service.persist_messages_and_snapshot([], snapshot=snapshot)
    service.persist_messages_and_snapshot(
        [],
        snapshot=snapshot.model_copy(update={"status": RunStatus.DECISIONS_RECORDED, "message_count": 2}),
    )

    session_factory = create_session_factory(database_url=sqlite_url(database_path))
    with session_factory() as session:
        rows = session.query(RunSnapshotRecord).all()

    assert len(rows) == 1
    assert rows[0].status == "decisions_recorded"
    assert rows[0].message_count == 2


def test_persisted_event_fields_match_the_source_message(tmp_path: Path) -> None:
    """Durable event rows should preserve the key canonical fields from the source message."""
    database_path = tmp_path / "coordinator.db"
    service = build_service(database_path)
    message = build_task_create_message()

    service.persist_messages_and_snapshot([message])

    session_factory = create_session_factory(database_url=sqlite_url(database_path))
    with session_factory() as session:
        row = session.query(ProtocolEvent).one()

    raw_message = json.loads(row.raw_message_json)
    payload = json.loads(row.payload_json)
    assert row.run_id == message.envelope.run_id
    assert row.task_id == message.envelope.task_id
    assert row.sender_id == message.envelope.sender_id
    assert row.recipient_id == message.envelope.recipient_id
    assert row.domain_id == message.envelope.domain_id
    assert row.trace_id == message.envelope.trace_id
    assert raw_message["envelope"]["message_id"] == message.envelope.message_id
    assert payload["title"] == message.payload.title


def test_persisted_snapshot_fields_match_the_in_memory_run_snapshot(tmp_path: Path) -> None:
    """Durable run snapshots should match the current in-memory projection."""
    database_path = tmp_path / "coordinator.db"
    service = build_service(database_path)
    store = InMemoryRunStore()
    message = build_task_create_message()
    snapshot = store.record_task_create(message)

    service.persist_messages_and_snapshot([message], snapshot=snapshot)

    session_factory = create_session_factory(database_url=sqlite_url(database_path))
    with session_factory() as session:
        row = session.query(RunSnapshotRecord).one()

    serialized_snapshot = json.loads(row.snapshot_json)
    assert row.run_id == snapshot.run_id
    assert row.task_id == snapshot.task_id
    assert row.status == snapshot.status
    assert row.last_message_type == snapshot.last_message_type
    assert row.message_count == snapshot.message_count
    assert serialized_snapshot == snapshot.model_dump(mode="json")


def test_load_run_snapshot_returns_the_persisted_snapshot(tmp_path: Path) -> None:
    """The persistence service should reconstruct durable run snapshots for DB-backed runtime reads."""
    database_path = tmp_path / "coordinator.db"
    service = build_service(database_path)
    store = InMemoryRunStore()
    message = build_task_create_message()
    snapshot = store.record_task_create(message)

    service.persist_messages_and_snapshot([message], snapshot=snapshot)

    loaded = service.load_run_snapshot(message.envelope.run_id)

    assert loaded is not None
    assert loaded.model_dump(mode="json") == snapshot.model_dump(mode="json")


def test_load_task_create_message_returns_the_original_persisted_message(tmp_path: Path) -> None:
    """The persistence service should recover the original task-create message for later dispatch."""
    database_path = tmp_path / "coordinator.db"
    service = build_service(database_path)
    message = build_task_create_message()

    service.persist_messages_and_snapshot([message])

    loaded = service.load_task_create_message(message.envelope.run_id)

    assert loaded is not None
    assert loaded.model_dump(mode="json") == message.model_dump(mode="json")

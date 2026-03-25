"""Write-through persistence helpers for coordinator runtime state."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Protocol

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from coordinator_api.db.models import ProtocolEvent, RunSnapshotRecord
from coordinator_api.service.state import RunSnapshot
from fap_core import message_from_dict, message_to_dict
from fap_core.clocks import utc_now
from fap_core.messages import MessageParseError, SupportedMessage, TaskCreateMessage, UnknownMessageKindError


class PersistenceError(Exception):
    """Raised when durable coordinator persistence fails."""


class PersistedEventSummary(BaseModel):
    """Stable summary view for persisted coordinator events."""

    model_config = ConfigDict(extra="forbid")

    message_id: str
    message_type: str
    sender_id: str
    recipient_id: str
    recorded_at: datetime


class PersistenceService(Protocol):
    """Protocol for coordinator persistence adapters."""

    def persist_messages_and_snapshot(
        self, messages: Sequence[SupportedMessage], *, snapshot: RunSnapshot | None = None
    ) -> None:
        """Persist canonical protocol events and an optional updated run snapshot."""

    def list_events_for_run(self, run_id: str) -> list[PersistedEventSummary]:
        """Return persisted event summaries for a coordinator run."""

    def load_run_snapshot(self, run_id: str) -> RunSnapshot | None:
        """Return the durable run snapshot for a run if present."""

    def load_task_create_message(self, run_id: str) -> TaskCreateMessage | None:
        """Return the original durable task-create message for a run if present."""


class CoordinatorPersistenceService:
    """SQLAlchemy-backed write-through persistence for coordinator runtime state."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def persist_messages_and_snapshot(
        self, messages: Sequence[SupportedMessage], *, snapshot: RunSnapshot | None = None
    ) -> None:
        """Persist canonical protocol events and optionally upsert a run snapshot."""
        if not messages and snapshot is None:
            return

        with self._session_factory() as session:
            try:
                for message in messages:
                    self._persist_message(session, message)
                if snapshot is not None:
                    self._upsert_run_snapshot(session, snapshot)
                session.commit()
            except Exception as exc:
                session.rollback()
                raise PersistenceError(
                    f"Failed to persist coordinator runtime state: {exc}"
                ) from exc

    def list_events_for_run(self, run_id: str) -> list[PersistedEventSummary]:
        """Return persisted event summaries for a run in stable insertion order."""
        try:
            with self._session_factory() as session:
                rows = session.scalars(
                    select(ProtocolEvent)
                    .where(ProtocolEvent.run_id == run_id)
                    .order_by(ProtocolEvent.id.asc())
                ).all()
        except Exception as exc:
            raise PersistenceError(f"Failed to load coordinator events: {exc}") from exc

        return [
            PersistedEventSummary(
                message_id=row.message_id,
                message_type=row.message_type,
                sender_id=row.sender_id,
                recipient_id=row.recipient_id,
                recorded_at=_ensure_timezone_aware(row.recorded_at),
            )
            for row in rows
        ]

    def load_run_snapshot(self, run_id: str) -> RunSnapshot | None:
        """Return the durable run snapshot for a run if present."""
        try:
            with self._session_factory() as session:
                row = session.get(RunSnapshotRecord, run_id)
        except Exception as exc:
            raise PersistenceError(f"Failed to load coordinator run snapshot: {exc}") from exc

        if row is None:
            return None

        try:
            return RunSnapshot.model_validate_json(row.snapshot_json)
        except Exception as exc:
            raise PersistenceError(
                f"Failed to parse coordinator run snapshot for run {run_id!r}: {exc}"
            ) from exc

    def load_task_create_message(self, run_id: str) -> TaskCreateMessage | None:
        """Return the original durable task-create message for a run if present."""
        try:
            with self._session_factory() as session:
                row = session.scalars(
                    select(ProtocolEvent)
                    .where(
                        ProtocolEvent.run_id == run_id,
                        ProtocolEvent.message_type == "fap.task.create",
                    )
                    .order_by(ProtocolEvent.id.asc())
                ).first()
        except Exception as exc:
            raise PersistenceError(f"Failed to load task-create message: {exc}") from exc

        if row is None:
            return None

        try:
            raw_message = json.loads(row.raw_message_json)
            if not isinstance(raw_message, dict):
                raise TypeError("persisted raw message is not a JSON object")
            parsed = message_from_dict(raw_message)
        except (TypeError, ValueError, MessageParseError, UnknownMessageKindError) as exc:
            raise PersistenceError(
                f"Failed to parse persisted task-create message for run {run_id!r}: {exc}"
            ) from exc

        if not isinstance(parsed, TaskCreateMessage):
            raise PersistenceError(
                f"Persisted task-create message for run {run_id!r} had unexpected type: "
                f"{parsed.envelope.message_type.value!r}"
            )

        return parsed

    def _persist_message(self, session: Session, message: SupportedMessage) -> None:
        """Persist a canonical FAP message as a protocol event row."""
        raw_message = message_to_dict(message)
        payload = raw_message["payload"]
        assert isinstance(payload, dict)

        session.add(
            ProtocolEvent(
                run_id=message.envelope.run_id,
                task_id=message.envelope.task_id,
                message_id=message.envelope.message_id,
                message_type=message.envelope.message_type.value,
                sender_id=message.envelope.sender_id,
                recipient_id=message.envelope.recipient_id,
                domain_id=message.envelope.domain_id,
                trace_id=message.envelope.trace_id,
                recorded_at=utc_now(),
                raw_message_json=_dump_json(raw_message),
                payload_json=_dump_json(payload),
            )
        )

    def _upsert_run_snapshot(self, session: Session, snapshot: RunSnapshot) -> None:
        """Create or update the latest durable coordinator snapshot for a run."""
        serialized_snapshot = _dump_json(snapshot.model_dump(mode="json"))
        record = session.get(RunSnapshotRecord, snapshot.run_id)
        if record is None:
            session.add(
                RunSnapshotRecord(
                    run_id=snapshot.run_id,
                    task_id=snapshot.task_id,
                    status=snapshot.status,
                    last_message_type=snapshot.last_message_type,
                    message_count=snapshot.message_count,
                    snapshot_json=serialized_snapshot,
                    updated_at=utc_now(),
                )
            )
            return

        record.task_id = snapshot.task_id
        record.status = snapshot.status
        record.last_message_type = snapshot.last_message_type
        record.message_count = snapshot.message_count
        record.snapshot_json = serialized_snapshot
        record.updated_at = utc_now()


def _dump_json(data: dict[str, object]) -> str:
    """Serialize canonical coordinator data to deterministic JSON text."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _ensure_timezone_aware(value: datetime) -> datetime:
    """Normalize persisted timestamps to timezone-aware UTC datetimes."""
    if value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)

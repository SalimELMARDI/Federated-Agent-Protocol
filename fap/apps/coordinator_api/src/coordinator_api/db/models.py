"""SQLAlchemy models for coordinator runtime persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for coordinator SQLAlchemy models."""


class ProtocolEvent(Base):
    """Durable record of a canonical protocol message handled by the coordinator."""

    __tablename__ = "protocol_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    task_id: Mapped[str] = mapped_column(String, index=True)
    message_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    message_type: Mapped[str] = mapped_column(String, index=True)
    sender_id: Mapped[str] = mapped_column(String)
    recipient_id: Mapped[str] = mapped_column(String)
    domain_id: Mapped[str] = mapped_column(String)
    trace_id: Mapped[str] = mapped_column(String, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_message_json: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text)


class RunSnapshotRecord(Base):
    """Durable projection of the latest coordinator run snapshot."""

    __tablename__ = "run_snapshots"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)
    last_message_type: Mapped[str] = mapped_column(String)
    message_count: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

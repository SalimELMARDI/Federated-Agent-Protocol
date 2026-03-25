"""Task creation message models for FAP."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from fap_core.enums import MessageType
from fap_core.messages.envelope import MessageEnvelope

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TaskCreatePayload(BaseModel):
    """Payload for creating a new federated task."""

    model_config = ConfigDict(extra="forbid")

    title: NonEmptyText
    description: NonEmptyText
    requested_capabilities: list[NonEmptyText] = Field(default_factory=list)
    input_query: NonEmptyText
    constraints: list[NonEmptyText] = Field(default_factory=list)
    deadline: datetime | None = None
    budget: str | None = None

    @field_validator("deadline")
    @classmethod
    def validate_deadline(cls, value: datetime | None) -> datetime | None:
        """Ensure optional deadlines always include timezone information."""
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("deadline must be timezone-aware")
        return value


class TaskCreateMessage(BaseModel):
    """Top-level task creation message."""

    model_config = ConfigDict(extra="forbid")

    envelope: MessageEnvelope
    payload: TaskCreatePayload

    @field_validator("envelope")
    @classmethod
    def validate_envelope(cls, value: MessageEnvelope) -> MessageEnvelope:
        """Ensure the envelope type matches the task create payload."""
        if value.message_type != MessageType.FAP_TASK_CREATE:
            raise ValueError("envelope.message_type must equal 'fap.task.create'")
        return value

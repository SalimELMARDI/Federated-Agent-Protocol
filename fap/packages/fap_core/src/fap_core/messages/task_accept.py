"""Task acceptance message models for FAP."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from fap_core.enums import MessageType
from fap_core.messages.envelope import MessageEnvelope

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TaskAcceptPayload(BaseModel):
    """Payload for a participant accepting a task."""

    model_config = ConfigDict(extra="forbid")

    participant_id: NonEmptyText
    accepted_capabilities: list[NonEmptyText] = Field(default_factory=list)
    constraints: list[NonEmptyText] = Field(default_factory=list)
    estimated_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    note: NonEmptyText | None = None


class TaskAcceptMessage(BaseModel):
    """Top-level task acceptance message."""

    model_config = ConfigDict(extra="forbid")

    envelope: MessageEnvelope
    payload: TaskAcceptPayload

    @field_validator("envelope")
    @classmethod
    def validate_envelope(cls, value: MessageEnvelope) -> MessageEnvelope:
        """Ensure the envelope type matches the task accept payload."""
        if value.message_type != MessageType.FAP_TASK_ACCEPT:
            raise ValueError("envelope.message_type must equal 'fap.task.accept'")
        return value

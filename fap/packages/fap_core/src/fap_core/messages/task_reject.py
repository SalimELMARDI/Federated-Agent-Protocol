"""Task rejection message models for FAP."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from fap_core.enums import MessageType
from fap_core.messages.envelope import MessageEnvelope

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TaskRejectPayload(BaseModel):
    """Payload for a participant rejecting a task."""

    model_config = ConfigDict(extra="forbid")

    participant_id: NonEmptyText
    reason: NonEmptyText
    retryable: bool = False
    details: NonEmptyText | None = None


class TaskRejectMessage(BaseModel):
    """Top-level task rejection message."""

    model_config = ConfigDict(extra="forbid")

    envelope: MessageEnvelope
    payload: TaskRejectPayload

    @field_validator("envelope")
    @classmethod
    def validate_envelope(cls, value: MessageEnvelope) -> MessageEnvelope:
        """Ensure the envelope type matches the task reject payload."""
        if value.message_type != MessageType.FAP_TASK_REJECT:
            raise ValueError("envelope.message_type must equal 'fap.task.reject'")
        return value

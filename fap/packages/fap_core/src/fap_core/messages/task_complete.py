"""Task completion message models for FAP."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from fap_core.enums import MessageType, TaskCompleteStatus
from fap_core.messages.envelope import MessageEnvelope
from fap_core.messages.source_refs import SourceRef

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TaskCompletePayload(BaseModel):
    """Payload for a participant completing a task."""

    model_config = ConfigDict(extra="forbid")

    participant_id: NonEmptyText
    status: TaskCompleteStatus
    summary: NonEmptyText
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    result_ref: NonEmptyText | None = None
    source_refs: list[SourceRef] = Field(default_factory=list)


class TaskCompleteMessage(BaseModel):
    """Top-level task completion message."""

    model_config = ConfigDict(extra="forbid")

    envelope: MessageEnvelope
    payload: TaskCompletePayload

    @field_validator("envelope")
    @classmethod
    def validate_envelope(cls, value: MessageEnvelope) -> MessageEnvelope:
        """Ensure the envelope type matches the task complete payload."""
        if value.message_type != MessageType.FAP_TASK_COMPLETE:
            raise ValueError("envelope.message_type must equal 'fap.task.complete'")
        return value

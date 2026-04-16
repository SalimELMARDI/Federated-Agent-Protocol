"""Participant status message models for FAP discovery."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from fap_core.enums import MessageType, ParticipantHealth
from fap_core.messages.envelope import MessageEnvelope

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ParticipantStatusPayload(BaseModel):
    """Live operational status for a participant."""

    model_config = ConfigDict(extra="forbid")

    participant_id: NonEmptyText
    domain_id: NonEmptyText
    health: ParticipantHealth
    accepting_tasks: bool = True
    load: int = Field(default=0, ge=0)
    available_capabilities: list[NonEmptyText] = Field(default_factory=list)
    status_note: NonEmptyText | None = None


class ParticipantStatusMessage(BaseModel):
    """Top-level participant status message."""

    model_config = ConfigDict(extra="forbid")

    envelope: MessageEnvelope
    payload: ParticipantStatusPayload

    @field_validator("envelope")
    @classmethod
    def validate_envelope(cls, value: MessageEnvelope) -> MessageEnvelope:
        """Ensure the envelope type matches the participant status payload."""
        if value.message_type != MessageType.FAP_PARTICIPANT_STATUS:
            raise ValueError("envelope.message_type must equal 'fap.participant.status'")
        return value

"""Participant profile message models for FAP discovery."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from fap_core.enums import (
    MessageType,
    ParticipantCostClass,
    ParticipantExecutionClass,
    ParticipantLatencyClass,
    PrivacyClass,
)
from fap_core.messages.envelope import MessageEnvelope

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ParticipantProfilePayload(BaseModel):
    """Capability and execution profile for a participant."""

    model_config = ConfigDict(extra="forbid")

    participant_id: NonEmptyText
    domain_id: NonEmptyText
    capabilities: list[NonEmptyText] = Field(default_factory=list)
    tools: list[NonEmptyText] = Field(default_factory=list)
    execution_class: ParticipantExecutionClass
    latency_class: ParticipantLatencyClass
    cost_class: ParticipantCostClass
    default_privacy_class: PrivacyClass
    supports_mcp: bool = False
    supports_followup: bool = False
    outbound_network_access: bool = False
    description: NonEmptyText | None = None


class ParticipantProfileMessage(BaseModel):
    """Top-level participant profile message."""

    model_config = ConfigDict(extra="forbid")

    envelope: MessageEnvelope
    payload: ParticipantProfilePayload

    @field_validator("envelope")
    @classmethod
    def validate_envelope(cls, value: MessageEnvelope) -> MessageEnvelope:
        """Ensure the envelope type matches the participant profile payload."""
        if value.message_type != MessageType.FAP_PARTICIPANT_PROFILE:
            raise ValueError("envelope.message_type must equal 'fap.participant.profile'")
        return value

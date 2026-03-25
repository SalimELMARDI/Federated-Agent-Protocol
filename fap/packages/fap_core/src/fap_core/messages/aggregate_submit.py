"""Aggregation submission message models for FAP."""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from fap_core.enums import AggregateContributionType, MessageType
from fap_core.messages.envelope import MessageEnvelope
from fap_core.messages.source_refs import SourceRef

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AggregateSubmitPayload(BaseModel):
    """Payload for a participant contribution to aggregation."""

    model_config = ConfigDict(extra="forbid")

    participant_id: NonEmptyText
    contribution_type: AggregateContributionType
    summary: NonEmptyText | None = None
    vote: NonEmptyText | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    provenance_ref: NonEmptyText | None = None
    source_refs: list[SourceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_summary_or_vote(self) -> AggregateSubmitPayload:
        """Ensure at least one contribution channel is populated."""
        if self.summary is None and self.vote is None:
            raise ValueError("at least one of summary or vote must be provided")
        return self


class AggregateSubmitMessage(BaseModel):
    """Top-level aggregation submission message."""

    model_config = ConfigDict(extra="forbid")

    envelope: MessageEnvelope
    payload: AggregateSubmitPayload

    @field_validator("envelope")
    @classmethod
    def validate_envelope(cls, value: MessageEnvelope) -> MessageEnvelope:
        """Ensure the envelope type matches the aggregate submit payload."""
        if value.message_type != MessageType.FAP_AGGREGATE_SUBMIT:
            raise ValueError("envelope.message_type must equal 'fap.aggregate.submit'")
        return value

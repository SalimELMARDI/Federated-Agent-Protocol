"""Aggregation result message models for FAP."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from fap_core.enums import AggregationMode, MessageType
from fap_core.messages.envelope import MessageEnvelope
from fap_core.messages.source_refs import SourceRef

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AggregateResultPayload(BaseModel):
    """Payload for the coordinator's aggregated result."""

    model_config = ConfigDict(extra="forbid")

    aggregation_mode: AggregationMode
    final_answer: NonEmptyText
    participant_count: int = Field(ge=0)
    provenance_refs: list[NonEmptyText] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class AggregateResultMessage(BaseModel):
    """Top-level aggregation result message."""

    model_config = ConfigDict(extra="forbid")

    envelope: MessageEnvelope
    payload: AggregateResultPayload

    @field_validator("envelope")
    @classmethod
    def validate_envelope(cls, value: MessageEnvelope) -> MessageEnvelope:
        """Ensure the envelope type matches the aggregate result payload."""
        if value.message_type != MessageType.FAP_AGGREGATE_RESULT:
            raise ValueError("envelope.message_type must equal 'fap.aggregate.result'")
        return value

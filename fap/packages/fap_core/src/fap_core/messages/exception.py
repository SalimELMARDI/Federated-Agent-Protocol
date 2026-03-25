"""Exception message models for FAP."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from fap_core.enums import MessageType
from fap_core.messages.envelope import MessageEnvelope

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ExceptionPayload(BaseModel):
    """Payload for exception messages exchanged by FAP services."""

    model_config = ConfigDict(extra="forbid")

    code: NonEmptyText
    message: NonEmptyText
    retryable: bool = False
    details: NonEmptyText | None = None


class ExceptionMessage(BaseModel):
    """Top-level exception message."""

    model_config = ConfigDict(extra="forbid")

    envelope: MessageEnvelope
    payload: ExceptionPayload

    @field_validator("envelope")
    @classmethod
    def validate_envelope(cls, value: MessageEnvelope) -> MessageEnvelope:
        """Ensure the envelope type matches the exception payload."""
        if value.message_type != MessageType.FAP_EXCEPTION:
            raise ValueError("envelope.message_type must equal 'fap.exception'")
        return value

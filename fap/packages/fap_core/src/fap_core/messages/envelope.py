"""Base envelope models for FAP messages."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from fap_core.enums import MessageType, PrivacyClass, ProtocolVersion, SharingMode

NonEmptyId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class GovernanceMetadata(BaseModel):
    """Optional governance metadata attached to a FAP message."""

    model_config = ConfigDict(extra="forbid")

    privacy_class: PrivacyClass | None = None
    sharing_mode: SharingMode | None = None
    policy_ref: str | None = None
    provenance_ref: str | None = None


class MessageEnvelope(BaseModel):
    """Protocol-level envelope shared by all FAP messages."""

    model_config = ConfigDict(extra="forbid")

    protocol: str = "FAP"
    version: ProtocolVersion = ProtocolVersion.V0_1
    message_type: MessageType
    task_id: NonEmptyId
    run_id: NonEmptyId
    message_id: NonEmptyId
    sender_id: NonEmptyId
    recipient_id: NonEmptyId
    domain_id: NonEmptyId
    trace_id: NonEmptyId
    timestamp: datetime
    governance: GovernanceMetadata | None = None

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, value: str) -> str:
        """Ensure the envelope uses the FAP protocol marker."""
        if value != "FAP":
            raise ValueError("protocol must equal 'FAP'")
        return value

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        """Ensure timestamps always include timezone information."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value

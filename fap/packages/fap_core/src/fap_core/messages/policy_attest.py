"""Policy attestation message models for FAP."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from fap_core.enums import (
    MessageType,
    PolicyTransformType,
    PrivacyClass,
    SharingMode,
)
from fap_core.messages.envelope import MessageEnvelope

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PolicyAttestPayload(BaseModel):
    """Payload describing how a participant applied policy controls."""

    model_config = ConfigDict(extra="forbid")

    participant_id: NonEmptyText
    policy_ref: NonEmptyText
    original_privacy_class: PrivacyClass
    applied_sharing_mode: SharingMode
    transform_type: PolicyTransformType
    attestation_note: NonEmptyText | None = None


class PolicyAttestMessage(BaseModel):
    """Top-level policy attestation message."""

    model_config = ConfigDict(extra="forbid")

    envelope: MessageEnvelope
    payload: PolicyAttestPayload

    @field_validator("envelope")
    @classmethod
    def validate_envelope(cls, value: MessageEnvelope) -> MessageEnvelope:
        """Ensure the envelope type matches the policy attestation payload."""
        if value.message_type != MessageType.FAP_POLICY_ATTEST:
            raise ValueError("envelope.message_type must equal 'fap.policy.attest'")
        return value

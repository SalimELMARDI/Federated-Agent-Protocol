"""Typed policy-engine models for executable FAP policy decisions."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from fap_core.enums import PrivacyClass, SharingMode
from fap_core.messages import PolicyAttestMessage

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class LocalResult(BaseModel):
    """Participant-local result prior to policy approval."""

    model_config = ConfigDict(extra="forbid")

    participant_id: NonEmptyText
    content: NonEmptyText
    privacy_class: PrivacyClass
    requested_sharing_mode: SharingMode


class PolicyEnvelopeContext(BaseModel):
    """Optional envelope context used to correlate policy attestations to a FAP run."""

    model_config = ConfigDict(extra="forbid")

    task_id: NonEmptyText
    run_id: NonEmptyText
    trace_id: NonEmptyText
    recipient_id: NonEmptyText
    sender_id: NonEmptyText
    domain_id: NonEmptyText


class ApprovedExport(BaseModel):
    """Policy-approved export derived from a local result."""

    model_config = ConfigDict(extra="forbid")

    content: str | None
    sharing_mode: SharingMode
    redactions_applied: bool


class PolicyDecision(BaseModel):
    """Complete result of applying a policy to a local participant result."""

    model_config = ConfigDict(extra="forbid")

    approved_export: ApprovedExport
    policy_attest_message: PolicyAttestMessage

"""Typed in-memory coordinator run state models."""

from __future__ import annotations

from fap_core.enums import (
    AggregateContributionType,
    AggregationMode,
    PolicyTransformType,
    PrivacyClass,
    RunStatus,
    SharingMode,
    TaskCompleteStatus,
)
from fap_core.messages import SourceRef
from pydantic import BaseModel, ConfigDict, Field


class RejectedParticipant(BaseModel):
    """Structured information about a participant rejection decision."""

    model_config = ConfigDict(extra="forbid")

    participant_id: str
    reason: str
    retryable: bool


class CompletedParticipant(BaseModel):
    """Structured information about a participant completion result."""

    model_config = ConfigDict(extra="forbid")

    participant_id: str
    status: TaskCompleteStatus
    summary: str
    message_id: str
    source_refs: list[SourceRef] = Field(default_factory=list)


class PolicyAttestationRecord(BaseModel):
    """Structured information about a recorded policy attestation."""

    model_config = ConfigDict(extra="forbid")

    participant_id: str
    policy_ref: str
    original_privacy_class: PrivacyClass
    applied_sharing_mode: SharingMode
    transform_type: PolicyTransformType
    message_id: str


class AggregateResultRecord(BaseModel):
    """Structured information about a recorded aggregate result."""

    model_config = ConfigDict(extra="forbid")

    aggregation_mode: AggregationMode
    final_answer: str
    participant_count: int = Field(ge=0)
    provenance_refs: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    message_id: str


class AggregateSubmissionRecord(BaseModel):
    """Structured information about a recorded aggregation input submission."""

    model_config = ConfigDict(extra="forbid")

    participant_id: str
    contribution_type: AggregateContributionType
    summary: str | None = None
    vote: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    provenance_ref: str | None = None
    source_refs: list[SourceRef] = Field(default_factory=list)
    message_id: str


class RunSnapshot(BaseModel):
    """Current in-memory snapshot of a coordinator-tracked run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    task_id: str
    status: RunStatus
    created_message_id: str | None = None
    last_message_type: str
    message_count: int = Field(ge=0)
    accepted_participants: list[str] = Field(default_factory=list)
    rejected_participants: list[RejectedParticipant] = Field(default_factory=list)
    completed_participants: list[CompletedParticipant] = Field(default_factory=list)
    policy_attestations: list[PolicyAttestationRecord] = Field(default_factory=list)
    aggregate_submissions: list[AggregateSubmissionRecord] = Field(default_factory=list)
    aggregate_results: list[AggregateResultRecord] = Field(default_factory=list)

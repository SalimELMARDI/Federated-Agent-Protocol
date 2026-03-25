"""Lightweight typed models for the external FAP Python client."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvaluationRecord(BaseModel):
    """Stable view of one orchestration evaluation step."""

    model_config = ConfigDict(extra="forbid")

    participant: str
    message_type: str
    accepted: bool


class ExecutionRecord(BaseModel):
    """Stable view of one orchestration execution step."""

    model_config = ConfigDict(extra="forbid")

    participant: str
    executed: bool
    message_type: str


class SourceRefResponse(BaseModel):
    """Stable view of one evidence source reference returned by the coordinator."""

    model_config = ConfigDict(extra="forbid")

    participant_id: str
    source_id: str
    source_title: str
    source_path: str


class AskResponse(BaseModel):
    """Typed response returned by the coordinator `/ask` API."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    task_id: str
    created_message_id: str
    final_answer: str
    source_refs: list[SourceRefResponse] = Field(default_factory=list)
    aggregate_result: dict[str, object]
    evaluations: list[EvaluationRecord] = Field(default_factory=list)
    executions: list[ExecutionRecord] = Field(default_factory=list)
    run_path: str
    events_path: str


class RunSnapshotResponse(BaseModel):
    """Lightweight typed run snapshot returned by the coordinator."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    task_id: str
    status: str
    created_message_id: str | None = None
    last_message_type: str
    message_count: int
    accepted_participants: list[str] = Field(default_factory=list)
    rejected_participants: list[dict[str, object]] = Field(default_factory=list)
    completed_participants: list[dict[str, object]] = Field(default_factory=list)
    policy_attestations: list[dict[str, object]] = Field(default_factory=list)
    aggregate_submissions: list[dict[str, object]] = Field(default_factory=list)
    aggregate_results: list[dict[str, object]] = Field(default_factory=list)


class PersistedEventSummary(BaseModel):
    """Typed summary of one persisted coordinator event."""

    model_config = ConfigDict(extra="forbid")

    message_id: str
    message_type: str
    sender_id: str
    recipient_id: str
    recorded_at: datetime


class RunEventsResponse(BaseModel):
    """Typed wrapper around the coordinator run-events API."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    events: list[PersistedEventSummary] = Field(default_factory=list)

    def message_types(self) -> list[str]:
        """Return persisted event types in stable response order."""
        return [event.message_type for event in self.events]

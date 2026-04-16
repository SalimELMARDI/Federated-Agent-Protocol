"""Thin user-facing agent wrapper built on top of the coordinator runtime."""

from __future__ import annotations

from typing import Annotated

import httpx
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from coordinator_api.service.orchestration import (
    OrchestrationResult,
    orchestrate_run_summary_merge,
)
from coordinator_api.service.persistence import PersistenceService
from coordinator_api.service.store import CoordinatorStore, InMemoryRunStore
from fap_core.clocks import utc_now
from fap_core.enums import MessageType, PrivacyClass, SharingMode
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import GovernanceMetadata, MessageEnvelope, TaskCreateMessage, TaskCreatePayload

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

DEFAULT_AGENT_POLICY_REF = "policy.agent.v0"
DEFAULT_AGENT_PRIVACY_CLASS = PrivacyClass.INTERNAL
DEFAULT_AGENT_SHARING_MODE = SharingMode.SUMMARY_ONLY
DEFAULT_AGENT_SENDER_ID = "fap_agent"
DEFAULT_AGENT_DOMAIN_ID = "agent"


class AgentAskRequest(BaseModel):
    """Plain user-facing request shape for the first FAP agent wrapper."""

    model_config = ConfigDict(extra="forbid")

    query: NonEmptyText
    title: NonEmptyText | None = None
    description: NonEmptyText | None = None
    requested_capabilities: list[NonEmptyText] = Field(default_factory=list)
    constraints: list[NonEmptyText] = Field(default_factory=list)
    governance: GovernanceMetadata | None = None


class AgentRunResult(BaseModel):
    """Structured result returned by the thin user-facing agent wrapper."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    task_id: str
    created_message_id: str
    orchestration: OrchestrationResult


async def run_agent_request_summary_merge(
    request: AgentAskRequest,
    *,
    store: CoordinatorStore,
    persistence_service: PersistenceService,
    participant_docs_evaluate_url: str,
    participant_docs_execute_url: str,
    participant_docs_transport: httpx.AsyncBaseTransport | None = None,
    participant_kb_evaluate_url: str,
    participant_kb_execute_url: str,
    participant_kb_transport: httpx.AsyncBaseTransport | None = None,
    participant_logs_evaluate_url: str,
    participant_logs_execute_url: str,
    participant_logs_transport: httpx.AsyncBaseTransport | None = None,
    participant_llm_evaluate_url: str | None = None,
    participant_llm_execute_url: str | None = None,
    participant_llm_transport: httpx.AsyncBaseTransport | None = None,
) -> AgentRunResult:
    """Convert a plain request into a canonical task-create and run orchestration.

    Security: participant_llm is only dispatched if the request explicitly includes
    at least one llm.* capability. This prevents automatic LLM participation in
    queries not intended for external transmission.
    """
    task_create_message = _build_task_create_message(request)
    snapshot = store.record_task_create(task_create_message)
    if isinstance(store, InMemoryRunStore):
        persistence_service.persist_messages_and_snapshot([task_create_message], snapshot=snapshot)

    # Security: Only dispatch to LLM if explicit llm.* capability requested
    # This provides coordinator-side defense-in-depth (participant-side also rejects)
    has_llm_capability = any(cap.startswith("llm.") for cap in request.requested_capabilities)
    effective_llm_evaluate_url = participant_llm_evaluate_url if has_llm_capability else None
    effective_llm_execute_url = participant_llm_execute_url if has_llm_capability else None
    effective_llm_transport = participant_llm_transport if has_llm_capability else None

    orchestration = await orchestrate_run_summary_merge(
        task_create_message.envelope.run_id,
        store=store,
        persistence_service=persistence_service,
        participant_docs_evaluate_url=participant_docs_evaluate_url,
        participant_docs_execute_url=participant_docs_execute_url,
        participant_docs_transport=participant_docs_transport,
        participant_kb_evaluate_url=participant_kb_evaluate_url,
        participant_kb_execute_url=participant_kb_execute_url,
        participant_kb_transport=participant_kb_transport,
        participant_logs_evaluate_url=participant_logs_evaluate_url,
        participant_logs_execute_url=participant_logs_execute_url,
        participant_logs_transport=participant_logs_transport,
        participant_llm_evaluate_url=effective_llm_evaluate_url,
        participant_llm_execute_url=effective_llm_execute_url,
        participant_llm_transport=effective_llm_transport,
    )

    return AgentRunResult(
        run_id=task_create_message.envelope.run_id,
        task_id=task_create_message.envelope.task_id,
        created_message_id=task_create_message.envelope.message_id,
        orchestration=orchestration,
    )


def _build_task_create_message(request: AgentAskRequest) -> TaskCreateMessage:
    """Build a canonical task-create message from a plain user-facing request."""
    title = request.title if request.title is not None else f"Federated request: {request.query}"
    description = (
        request.description
        if request.description is not None
        else f"Execute a governed federated review for the user request: {request.query}"
    )

    return TaskCreateMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_CREATE,
            task_id=new_task_id(),
            run_id=new_run_id(),
            message_id=new_message_id(),
            sender_id=DEFAULT_AGENT_SENDER_ID,
            recipient_id="coordinator",
            domain_id=DEFAULT_AGENT_DOMAIN_ID,
            trace_id=new_trace_id(),
            timestamp=utc_now(),
            governance=_resolve_governance(request.governance),
        ),
        payload=TaskCreatePayload(
            title=title,
            description=description,
            requested_capabilities=list(request.requested_capabilities),
            input_query=request.query,
            constraints=list(request.constraints),
        ),
    )


def _resolve_governance(governance: GovernanceMetadata | None) -> GovernanceMetadata:
    """Resolve the effective governance defaults for the user-facing wrapper."""
    if governance is not None:
        return governance

    return GovernanceMetadata(
        privacy_class=DEFAULT_AGENT_PRIVACY_CLASS,
        sharing_mode=DEFAULT_AGENT_SHARING_MODE,
        policy_ref=DEFAULT_AGENT_POLICY_REF,
    )

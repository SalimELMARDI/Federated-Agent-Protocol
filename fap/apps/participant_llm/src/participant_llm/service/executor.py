"""LLM-backed participant_llm execution service."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from fap_core.clocks import utc_now
from fap_core.enums import (
    AggregateContributionType,
    MessageType,
    PrivacyClass,
    SharingMode,
    TaskCompleteStatus,
)
from fap_core.ids import new_message_id
from fap_core.messages import (
    AggregateSubmitMessage,
    AggregateSubmitPayload,
    GovernanceMetadata,
    MessageEnvelope,
    PolicyAttestMessage,
    SourceRef,
    TaskCompleteMessage,
    TaskCompletePayload,
    TaskCreateMessage,
)
from fap_core.policy import LocalResult, PolicyEnvelopeContext, apply_policy
from participant_llm.adapters.llm_client import LLMResponse, call_llm

PARTICIPANT_ID = "participant_llm"
DOMAIN_ID = "participant_llm"
DEFAULT_PRIVACY_CLASS = PrivacyClass.INTERNAL
DEFAULT_SHARING_MODE = SharingMode.SUMMARY_ONLY
DEFAULT_POLICY_REF = "policy.llm.v0"
VOTE_ONLY_SUMMARY = "[VOTE ONLY] No content exported"


class ParticipantExecutionResult(BaseModel):
    """Canonical result bundle returned by participant_llm execution."""

    model_config = ConfigDict(extra="forbid")

    task_complete_message: TaskCompleteMessage
    policy_attest_message: PolicyAttestMessage
    aggregate_submit_message: AggregateSubmitMessage


async def execute_task_create(message: TaskCreateMessage) -> ParticipantExecutionResult:
    """Execute a task-create request against the configured LLM and apply shared policy."""
    local_content, source_refs = await _query_llm_and_build_source_refs(message.payload.input_query)
    governance = message.envelope.governance
    local_result = LocalResult(
        participant_id=PARTICIPANT_ID,
        content=local_content,
        privacy_class=_derive_privacy_class(governance),
        requested_sharing_mode=_derive_requested_sharing_mode(governance),
    )
    policy_ref = _derive_policy_ref(governance)
    policy_decision = apply_policy(
        local_result,
        policy_ref=policy_ref,
        envelope_context=PolicyEnvelopeContext(
            task_id=message.envelope.task_id,
            run_id=message.envelope.run_id,
            trace_id=message.envelope.trace_id,
            recipient_id=message.envelope.sender_id,
            sender_id=PARTICIPANT_ID,
            domain_id=DOMAIN_ID,
        ),
    )
    governed_summary = policy_decision.approved_export.content or VOTE_ONLY_SUMMARY

    task_complete_message = TaskCompleteMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_COMPLETE,
            task_id=message.envelope.task_id,
            run_id=message.envelope.run_id,
            message_id=new_message_id(),
            sender_id=PARTICIPANT_ID,
            recipient_id=message.envelope.sender_id,
            domain_id=DOMAIN_ID,
            trace_id=message.envelope.trace_id,
            timestamp=utc_now(),
        ),
        payload=TaskCompletePayload(
            participant_id=PARTICIPANT_ID,
            status=TaskCompleteStatus.COMPLETED,
            summary=governed_summary,
            source_refs=source_refs,
        ),
    )
    aggregate_submit_message = AggregateSubmitMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_AGGREGATE_SUBMIT,
            task_id=message.envelope.task_id,
            run_id=message.envelope.run_id,
            message_id=new_message_id(),
            sender_id=PARTICIPANT_ID,
            recipient_id=message.envelope.sender_id,
            domain_id=DOMAIN_ID,
            trace_id=message.envelope.trace_id,
            timestamp=utc_now(),
        ),
        payload=AggregateSubmitPayload(
            participant_id=PARTICIPANT_ID,
            contribution_type=AggregateContributionType.SUMMARY,
            summary=governed_summary,
            provenance_ref=policy_decision.policy_attest_message.envelope.message_id,
            source_refs=source_refs,
        ),
    )

    return ParticipantExecutionResult(
        task_complete_message=task_complete_message,
        policy_attest_message=policy_decision.policy_attest_message,
        aggregate_submit_message=aggregate_submit_message,
    )


async def _query_llm_and_build_source_refs(query: str) -> tuple[str, list[SourceRef]]:
    """Call the LLM with the query and build deterministic source refs from the response.

    Raises:
        LLMCallError: Upstream LLM provider call failed. Caller should handle by
                      returning HTTP 503 to signal execution failure to coordinator.
    """
    # Let LLMCallError propagate instead of catching and converting to string
    # This makes LLM failures protocol-visible (HTTP 503) rather than treating
    # them as successful task completions with error strings
    llm_response = await call_llm(query)
    source_refs = _build_source_refs(llm_response)
    return llm_response.content, source_refs


def _build_source_refs(llm_response: LLMResponse) -> list[SourceRef]:
    """Build deterministic source refs from the LLM response metadata."""
    return [
        SourceRef(
            participant_id=PARTICIPANT_ID,
            source_id=llm_response.model,
            source_title=f"LLM: {llm_response.model}",
            source_path=llm_response.endpoint_url,
        )
    ]


def _derive_privacy_class(governance: GovernanceMetadata | None) -> PrivacyClass:
    """Resolve the effective privacy class for local execution."""
    if governance is None or governance.privacy_class is None:
        return DEFAULT_PRIVACY_CLASS
    return governance.privacy_class


def _derive_requested_sharing_mode(governance: GovernanceMetadata | None) -> SharingMode:
    """Resolve the effective sharing mode requested by the coordinator."""
    if governance is None or governance.sharing_mode is None:
        return DEFAULT_SHARING_MODE
    return governance.sharing_mode


def _derive_policy_ref(governance: GovernanceMetadata | None) -> str:
    """Resolve the policy reference used for the shared policy engine."""
    if governance is None or governance.policy_ref is None:
        return DEFAULT_POLICY_REF
    return governance.policy_ref

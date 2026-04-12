"""Evaluation logic for participant_llm task-create messages."""

from __future__ import annotations

from fap_core.clocks import utc_now
from fap_core.enums import MessageType
from fap_core.ids import new_message_id
from fap_core.messages import (
    MessageEnvelope,
    TaskAcceptMessage,
    TaskAcceptPayload,
    TaskCreateMessage,
    TaskRejectMessage,
    TaskRejectPayload,
)
from participant_llm.service.capabilities import get_supported_capabilities

PARTICIPANT_ID = "participant_llm"
DOMAIN_ID = "participant_llm"


def _build_response_envelope(
    message: TaskCreateMessage, *, message_type: MessageType
) -> MessageEnvelope:
    """Build a canonical response envelope derived from an inbound task create message."""
    return MessageEnvelope(
        message_type=message_type,
        task_id=message.envelope.task_id,
        run_id=message.envelope.run_id,
        message_id=new_message_id(),
        sender_id=PARTICIPANT_ID,
        recipient_id=message.envelope.sender_id,
        domain_id=DOMAIN_ID,
        trace_id=message.envelope.trace_id,
        timestamp=utc_now(),
    )


def evaluate_task_create(message: TaskCreateMessage) -> TaskAcceptMessage | TaskRejectMessage:
    """Evaluate a task-create message against the participant_llm capability profile.

    Security constraint: This participant ONLY accepts requests that explicitly include
    at least one llm.* capability. Empty or non-LLM capability requests are rejected to
    prevent automatic participation in sensitive queries that were not intended for
    external LLM transmission.

    This aligns with the trust model: input queries are sent to external LLM providers
    before governance, so participation must be explicitly requested per task.
    """
    supported_capabilities = get_supported_capabilities()
    requested_capabilities = message.payload.requested_capabilities

    # Security: Reject empty capability requests (no auto-accept)
    # The LLM participant must be explicitly requested via llm.* capabilities
    if not requested_capabilities:
        return TaskRejectMessage(
            envelope=_build_response_envelope(message, message_type=MessageType.FAP_TASK_REJECT),
            payload=TaskRejectPayload(
                participant_id=PARTICIPANT_ID,
                reason=(
                    "participant_llm requires explicit llm.* capabilities. "
                    "Empty capability requests are rejected to prevent automatic "
                    "participation in queries not intended for external LLM transmission."
                ),
                retryable=False,
            ),
        )

    # Security: Reject requests that don't include at least one llm.* capability
    # This ensures the coordinator explicitly intended to use the LLM participant
    has_llm_capability = any(cap.startswith("llm.") for cap in requested_capabilities)
    if not has_llm_capability:
        return TaskRejectMessage(
            envelope=_build_response_envelope(message, message_type=MessageType.FAP_TASK_REJECT),
            payload=TaskRejectPayload(
                participant_id=PARTICIPANT_ID,
                reason=(
                    "participant_llm requires at least one llm.* capability "
                    "(llm.query, llm.summarize, llm.reason). Requests without explicit "
                    "LLM capabilities are rejected to prevent unintended external transmission."
                ),
                retryable=False,
            ),
        )

    # Federation-aware filtering: only check capabilities belonging to this domain.
    # Capabilities for other participants (e.g. docs.*, kb.*) are ignored by this evaluator.
    unsupported_capabilities = [
        capability
        for capability in requested_capabilities
        if capability.startswith("llm.") and capability not in supported_capabilities
    ]

    if unsupported_capabilities:
        unsupported_list = ", ".join(unsupported_capabilities)
        return TaskRejectMessage(
            envelope=_build_response_envelope(message, message_type=MessageType.FAP_TASK_REJECT),
            payload=TaskRejectPayload(
                participant_id=PARTICIPANT_ID,
                reason=f"Unsupported capabilities requested: {unsupported_list}",
                retryable=False,
            ),
        )

    # Note: We only accept llm.* capabilities.  If other capabilities are provided, we ignore them.
    # The accepted list should only contains those we actually support.
    final_accepted = [cap for cap in requested_capabilities if cap in supported_capabilities]

    return TaskAcceptMessage(
        envelope=_build_response_envelope(message, message_type=MessageType.FAP_TASK_ACCEPT),
        payload=TaskAcceptPayload(
            participant_id=PARTICIPANT_ID,
            accepted_capabilities=final_accepted,
        ),
    )

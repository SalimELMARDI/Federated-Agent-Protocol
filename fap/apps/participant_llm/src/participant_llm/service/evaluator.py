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
    """Evaluate a task-create message against the participant_llm capability profile."""
    supported_capabilities = get_supported_capabilities()
    requested_capabilities = message.payload.requested_capabilities

    if not requested_capabilities:
        accepted_capabilities = list(supported_capabilities)
        return TaskAcceptMessage(
            envelope=_build_response_envelope(message, message_type=MessageType.FAP_TASK_ACCEPT),
            payload=TaskAcceptPayload(
                participant_id=PARTICIPANT_ID,
                accepted_capabilities=accepted_capabilities,
            ),
        )

    unsupported_capabilities = [
        capability
        for capability in requested_capabilities
        if capability not in supported_capabilities
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

    return TaskAcceptMessage(
        envelope=_build_response_envelope(message, message_type=MessageType.FAP_TASK_ACCEPT),
        payload=TaskAcceptPayload(
            participant_id=PARTICIPANT_ID,
            accepted_capabilities=list(requested_capabilities),
        ),
    )

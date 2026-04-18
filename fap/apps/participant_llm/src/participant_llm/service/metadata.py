"""Participant discovery metadata for the participant_llm service."""

from __future__ import annotations

from fap_core.clocks import utc_now
from fap_core.enums import (
    MessageType,
    ParticipantCostClass,
    ParticipantExecutionClass,
    ParticipantHealth,
    ParticipantLatencyClass,
)
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.identity import COORDINATOR_ID
from fap_core.messages import (
    MessageEnvelope,
    ParticipantProfileMessage,
    ParticipantProfilePayload,
    ParticipantStatusMessage,
    ParticipantStatusPayload,
)
from participant_llm.config import get_llm_model, get_llm_provider, is_participant_llm_enabled
from participant_llm.service.capabilities import get_supported_capabilities
from participant_llm.service.executor import DEFAULT_PRIVACY_CLASS, DOMAIN_ID, PARTICIPANT_ID

SUPPORTED_TOOLS: tuple[str, ...] = ("llm.provider.request",)
PROFILE_DESCRIPTION = (
    "Outbound LLM-backed participant for explicitly requested llm.* tasks."
)


def build_profile_message() -> ParticipantProfileMessage:
    """Return a canonical participant profile message."""
    provider = get_llm_provider()
    model = get_llm_model()
    return ParticipantProfileMessage(
        envelope=_build_envelope(MessageType.FAP_PARTICIPANT_PROFILE),
        payload=ParticipantProfilePayload(
            participant_id=PARTICIPANT_ID,
            domain_id=DOMAIN_ID,
            capabilities=list(get_supported_capabilities()),
            tools=list(SUPPORTED_TOOLS),
            execution_class=ParticipantExecutionClass.OUTBOUND,
            latency_class=ParticipantLatencyClass.INTERACTIVE,
            cost_class=ParticipantCostClass.MEDIUM,
            default_privacy_class=DEFAULT_PRIVACY_CLASS,
            supports_mcp=False,
            supports_followup=False,
            outbound_network_access=True,
            description=f"{PROFILE_DESCRIPTION} Provider={provider}, model={model}.",
        ),
    )


def build_status_message() -> ParticipantStatusMessage:
    """Return a canonical participant status message."""
    enabled = is_participant_llm_enabled()
    health = ParticipantHealth.OK if enabled else ParticipantHealth.DEGRADED
    available_capabilities = list(get_supported_capabilities()) if enabled else []
    if enabled:
        status_note = (
            f"Outbound execution enabled via {get_llm_provider()} using model {get_llm_model()}."
        )
    else:
        status_note = "Outbound execution disabled until PARTICIPANT_LLM_ENABLE=true is set."

    return ParticipantStatusMessage(
        envelope=_build_envelope(MessageType.FAP_PARTICIPANT_STATUS),
        payload=ParticipantStatusPayload(
            participant_id=PARTICIPANT_ID,
            domain_id=DOMAIN_ID,
            health=health,
            accepting_tasks=enabled,
            load=0,
            available_capabilities=available_capabilities,
            status_note=status_note,
        ),
    )


def _build_envelope(message_type: MessageType) -> MessageEnvelope:
    """Build a canonical discovery envelope for the participant."""
    return MessageEnvelope(
        message_type=message_type,
        task_id=new_task_id(),
        run_id=new_run_id(),
        message_id=new_message_id(),
        sender_id=PARTICIPANT_ID,
        recipient_id=COORDINATOR_ID.value,
        domain_id=DOMAIN_ID,
        trace_id=new_trace_id(),
        timestamp=utc_now(),
    )

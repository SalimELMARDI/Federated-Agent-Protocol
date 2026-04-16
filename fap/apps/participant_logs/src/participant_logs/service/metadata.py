"""Participant discovery metadata for the logs participant."""

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
from participant_logs.service.capabilities import get_supported_capabilities
from participant_logs.service.executor import DEFAULT_PRIVACY_CLASS, DOMAIN_ID, PARTICIPANT_ID

SUPPORTED_TOOLS: tuple[str, ...] = (
    "local_logs.load_logs",
    "local_logs.search_logs",
)
PROFILE_DESCRIPTION = (
    "Local observability participant for application and infrastructure log evidence."
)
STATUS_NOTE = "Ready for interactive local log and event queries."


def build_profile_message() -> ParticipantProfileMessage:
    """Return a canonical participant profile message."""
    return ParticipantProfileMessage(
        envelope=_build_envelope(MessageType.FAP_PARTICIPANT_PROFILE),
        payload=ParticipantProfilePayload(
            participant_id=PARTICIPANT_ID,
            domain_id=DOMAIN_ID,
            capabilities=list(get_supported_capabilities()),
            tools=list(SUPPORTED_TOOLS),
            execution_class=ParticipantExecutionClass.LOCAL,
            latency_class=ParticipantLatencyClass.INTERACTIVE,
            cost_class=ParticipantCostClass.LOW,
            default_privacy_class=DEFAULT_PRIVACY_CLASS,
            supports_mcp=False,
            supports_followup=False,
            outbound_network_access=False,
            description=PROFILE_DESCRIPTION,
        ),
    )


def build_status_message() -> ParticipantStatusMessage:
    """Return a canonical participant status message."""
    return ParticipantStatusMessage(
        envelope=_build_envelope(MessageType.FAP_PARTICIPANT_STATUS),
        payload=ParticipantStatusPayload(
            participant_id=PARTICIPANT_ID,
            domain_id=DOMAIN_ID,
            health=ParticipantHealth.OK,
            accepting_tasks=True,
            load=0,
            available_capabilities=list(get_supported_capabilities()),
            status_note=STATUS_NOTE,
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

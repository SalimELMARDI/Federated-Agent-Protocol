"""Unit tests for participant_llm capability evaluation.

Covers the accept/reject decision paths, capability negotiation details, and
envelope correlation guarantees of the participant_llm evaluator.
"""

from __future__ import annotations

from fap_core.clocks import utc_now
from fap_core.enums import MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import (
    MessageEnvelope,
    TaskAcceptMessage,
    TaskCreateMessage,
    TaskCreatePayload,
    TaskRejectMessage,
)
from participant_llm.service.capabilities import SUPPORTED_CAPABILITIES
from participant_llm.service.evaluator import evaluate_task_create


def _build_task_create(requested_capabilities: list[str]) -> TaskCreateMessage:
    return TaskCreateMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_CREATE,
            task_id=new_task_id(),
            run_id=new_run_id(),
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id="participant_llm",
            domain_id="participant_llm",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
        ),
        payload=TaskCreatePayload(
            title="LLM query",
            description="Query the LLM with governance applied.",
            requested_capabilities=requested_capabilities,
            input_query="What are the privacy implications?",
        ),
    )


# ---------------------------------------------------------------------------
# Accept paths
# ---------------------------------------------------------------------------


def test_accepts_llm_query_capability() -> None:
    """llm.query alone should produce a task-accept with that capability confirmed."""
    decision = evaluate_task_create(_build_task_create(["llm.query"]))

    assert isinstance(decision, TaskAcceptMessage)
    assert decision.payload.accepted_capabilities == ["llm.query"]


def test_accepts_all_three_supported_capabilities_together() -> None:
    """All three llm.* capabilities requested at once should all be confirmed."""
    caps = ["llm.query", "llm.summarize", "llm.reason"]
    decision = evaluate_task_create(_build_task_create(caps))

    assert isinstance(decision, TaskAcceptMessage)
    assert decision.payload.accepted_capabilities == caps


def test_empty_capabilities_rejects_to_prevent_auto_participation() -> None:
    """Empty capability list should REJECT to prevent automatic LLM participation.

    Security constraint: The LLM participant must be explicitly requested via llm.*
    capabilities. Auto-accepting empty requests would cause this participant to join
    all queries by default, including sensitive ones not intended for external LLM
    transmission.
    """
    decision = evaluate_task_create(_build_task_create([]))

    assert isinstance(decision, TaskRejectMessage)
    assert decision.payload.retryable is False
    assert "llm.*" in decision.payload.reason.lower() or "explicit" in decision.payload.reason.lower()


def test_supported_capabilities_set_contains_expected_entries() -> None:
    """The supported capabilities constant must cover the three LLM task types."""
    assert "llm.query" in SUPPORTED_CAPABILITIES
    assert "llm.summarize" in SUPPORTED_CAPABILITIES
    assert "llm.reason" in SUPPORTED_CAPABILITIES


# ---------------------------------------------------------------------------
# Reject paths
# ---------------------------------------------------------------------------


def test_rejects_single_unsupported_capability_without_llm_capability() -> None:
    """Non-LLM capability alone should reject (requires explicit llm.* capability)."""
    decision = evaluate_task_create(_build_task_create(["docs.search"]))

    assert isinstance(decision, TaskRejectMessage)
    assert decision.payload.retryable is False
    # Should reject because no llm.* capability present (earlier check)
    assert "llm." in decision.payload.reason.lower()


def test_accepts_and_ignores_non_llm_capabilities() -> None:
    """Non-LLM capabilities (e.g. kb.lookup) should be ignored if at least one llm.* capability is present."""
    decision = evaluate_task_create(_build_task_create(["llm.query", "kb.lookup"]))

    assert isinstance(decision, TaskAcceptMessage)
    # kb.lookup should be stripped from the accepted list
    assert decision.payload.accepted_capabilities == ["llm.query"]


def test_rejects_and_names_all_unsupported_llm_capabilities_in_reason() -> None:
    """Multiple unsupported llm.* capabilities must all appear in the reject reason."""
    decision = evaluate_task_create(
        _build_task_create(["llm.query", "llm.unknown", "llm.invalid"])
    )

    assert isinstance(decision, TaskRejectMessage)
    assert "llm.unknown" in decision.payload.reason
    assert "llm.invalid" in decision.payload.reason


# ---------------------------------------------------------------------------
# Envelope correlation
# ---------------------------------------------------------------------------


def test_response_envelope_mirrors_task_run_and_trace_ids() -> None:
    """The response envelope must carry the exact task/run/trace IDs from the request."""
    inbound = _build_task_create(["llm.query"])
    decision = evaluate_task_create(inbound)

    assert decision.envelope.task_id == inbound.envelope.task_id
    assert decision.envelope.run_id == inbound.envelope.run_id
    assert decision.envelope.trace_id == inbound.envelope.trace_id


def test_response_envelope_sets_participant_routing() -> None:
    """The response envelope must route from participant_llm back to the coordinator."""
    inbound = _build_task_create(["llm.query"])
    decision = evaluate_task_create(inbound)

    assert decision.envelope.sender_id == "participant_llm"
    assert decision.envelope.recipient_id == inbound.envelope.sender_id
    assert decision.envelope.domain_id == "participant_llm"


def test_reject_envelope_carries_correct_message_type() -> None:
    """A reject decision envelope must use the FAP_TASK_REJECT message type."""
    decision = evaluate_task_create(_build_task_create(["unsupported.cap"]))

    assert decision.envelope.message_type == MessageType.FAP_TASK_REJECT


def test_accept_envelope_carries_correct_message_type() -> None:
    """An accept decision envelope must use the FAP_TASK_ACCEPT message type."""
    decision = evaluate_task_create(_build_task_create(["llm.query"]))

    assert decision.envelope.message_type == MessageType.FAP_TASK_ACCEPT

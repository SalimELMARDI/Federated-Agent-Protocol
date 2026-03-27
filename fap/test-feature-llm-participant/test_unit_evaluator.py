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


def test_empty_capabilities_returns_full_profile_acceptance() -> None:
    """An empty capability list should accept and return the full supported profile."""
    decision = evaluate_task_create(_build_task_create([]))

    assert isinstance(decision, TaskAcceptMessage)
    assert set(decision.payload.accepted_capabilities) == set(SUPPORTED_CAPABILITIES)


def test_supported_capabilities_set_contains_expected_entries() -> None:
    """The supported capabilities constant must cover the three LLM task types."""
    assert "llm.query" in SUPPORTED_CAPABILITIES
    assert "llm.summarize" in SUPPORTED_CAPABILITIES
    assert "llm.reason" in SUPPORTED_CAPABILITIES


# ---------------------------------------------------------------------------
# Reject paths
# ---------------------------------------------------------------------------


def test_rejects_single_unsupported_capability() -> None:
    """One unsupported capability should produce a non-retryable reject."""
    decision = evaluate_task_create(_build_task_create(["docs.search"]))

    assert isinstance(decision, TaskRejectMessage)
    assert decision.payload.retryable is False
    assert "docs.search" in decision.payload.reason


def test_rejects_mix_of_supported_and_unsupported_capabilities() -> None:
    """A mix must reject — the unsupported capability name must appear in the reason."""
    decision = evaluate_task_create(_build_task_create(["llm.query", "kb.lookup"]))

    assert isinstance(decision, TaskRejectMessage)
    assert "kb.lookup" in decision.payload.reason


def test_rejects_and_names_all_unsupported_capabilities_in_reason() -> None:
    """Multiple unsupported capabilities must all appear in the reject reason."""
    decision = evaluate_task_create(
        _build_task_create(["llm.query", "docs.search", "logs.tail"])
    )

    assert isinstance(decision, TaskRejectMessage)
    assert "docs.search" in decision.payload.reason
    assert "logs.tail" in decision.payload.reason


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

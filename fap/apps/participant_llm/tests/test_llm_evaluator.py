"""Tests for the participant_llm task-create evaluator."""

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
from participant_llm.service.evaluator import evaluate_task_create


def build_task_create_message(requested_capabilities: list[str]) -> TaskCreateMessage:
    """Return a valid task-create message for evaluator tests."""
    return TaskCreateMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_CREATE,
            task_id=new_task_id(),
            run_id=new_run_id(),
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id="participant_llm",
            domain_id="llm",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
        ),
        payload=TaskCreatePayload(
            title="Query the LLM",
            description="Use an LLM to answer a federated query.",
            requested_capabilities=requested_capabilities,
            input_query="What are the privacy implications of this data?",
        ),
    )


def test_accepts_when_all_requested_capabilities_are_supported() -> None:
    """Supported requested capabilities should yield an accept decision."""
    inbound = build_task_create_message(["llm.query", "llm.summarize"])

    decision = evaluate_task_create(inbound)

    assert isinstance(decision, TaskAcceptMessage)
    assert decision.payload.accepted_capabilities == ["llm.query", "llm.summarize"]


def test_rejects_when_requested_capabilities_is_empty() -> None:
    """Empty requested capabilities should yield a reject decision (security constraint)."""
    inbound = build_task_create_message([])

    decision = evaluate_task_create(inbound)

    assert isinstance(decision, TaskRejectMessage)
    assert "participant_llm requires explicit llm.* capabilities" in decision.payload.reason


def test_accepts_when_non_llm_capabilities_are_present() -> None:
    """Non-LLM capabilities (e.g. docs.search) should be ignored if at least one llm.* capability is present."""
    inbound = build_task_create_message(["llm.query", "docs.search"])

    decision = evaluate_task_create(inbound)

    assert isinstance(decision, TaskAcceptMessage)
    # docs.search should be stripped from the accepted list
    assert decision.payload.accepted_capabilities == ["llm.query"]


def test_rejects_when_unsupported_llm_capabilities_are_requested() -> None:
    """Unsupported capabilities within the llm.* namespace should yield a reject decision."""
    inbound = build_task_create_message(["llm.query", "llm.future_tech"])

    decision = evaluate_task_create(inbound)

    assert isinstance(decision, TaskRejectMessage)
    assert "llm.future_tech" in decision.payload.reason


def test_response_envelope_preserves_task_run_and_trace_ids() -> None:
    """Response envelope should preserve the correlated task/run/trace values."""
    inbound = build_task_create_message(["llm.query"])

    decision = evaluate_task_create(inbound)

    assert decision.envelope.task_id == inbound.envelope.task_id
    assert decision.envelope.run_id == inbound.envelope.run_id
    assert decision.envelope.trace_id == inbound.envelope.trace_id


def test_response_envelope_sets_sender_recipient_and_message_type_correctly() -> None:
    """Response envelope should set participant routing and the correct decision type."""
    inbound = build_task_create_message(["llm.query", "llm.unsupported"])

    decision = evaluate_task_create(inbound)

    assert decision.envelope.sender_id == "participant_llm"
    assert decision.envelope.recipient_id == inbound.envelope.sender_id
    assert decision.envelope.domain_id == "participant_llm"
    assert decision.envelope.message_type == MessageType.FAP_TASK_REJECT

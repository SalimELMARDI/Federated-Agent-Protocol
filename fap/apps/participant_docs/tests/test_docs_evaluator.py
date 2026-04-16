"""Tests for the participant_docs task-create evaluator."""

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
from participant_docs.service.capabilities import SUPPORTED_CAPABILITIES
from participant_docs.service.evaluator import evaluate_task_create


def build_task_create_message(requested_capabilities: list[str]) -> TaskCreateMessage:
    """Return a valid task-create message for evaluator tests."""
    return TaskCreateMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_CREATE,
            task_id=new_task_id(),
            run_id=new_run_id(),
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id="participant_docs",
            domain_id="docs",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
        ),
        payload=TaskCreatePayload(
            title="Summarize notes",
            description="Create a redacted summary for coordinator review.",
            requested_capabilities=requested_capabilities,
            input_query="Summarize the incident notes.",
        ),
    )


def test_accepts_when_all_requested_capabilities_are_supported() -> None:
    """Supported requested capabilities should yield an accept decision."""
    inbound = build_task_create_message(["docs.lookup", "docs.summarize"])

    decision = evaluate_task_create(inbound)

    assert isinstance(decision, TaskAcceptMessage)
    assert decision.payload.accepted_capabilities == ["docs.lookup", "docs.summarize"]


def test_accepts_only_docs_capabilities_from_mixed_requests() -> None:
    """Mixed-domain capability requests should only echo docs-supported capabilities."""
    inbound = build_task_create_message(["docs.lookup", "llm.query"])

    decision = evaluate_task_create(inbound)

    assert isinstance(decision, TaskAcceptMessage)
    assert decision.payload.accepted_capabilities == ["docs.lookup"]


def test_accepts_when_requested_capabilities_is_empty() -> None:
    """Empty requested capabilities should yield full-profile acceptance."""
    inbound = build_task_create_message([])

    decision = evaluate_task_create(inbound)

    assert isinstance(decision, TaskAcceptMessage)
    assert decision.payload.accepted_capabilities == list(SUPPORTED_CAPABILITIES)


def test_rejects_when_one_unsupported_capability_is_requested() -> None:
    """A single unsupported capability should yield a reject decision."""
    inbound = build_task_create_message(["docs.search", "docs.translate"])

    decision = evaluate_task_create(inbound)

    assert isinstance(decision, TaskRejectMessage)
    assert decision.payload.retryable is False
    assert "docs.translate" in decision.payload.reason


def test_rejects_when_multiple_unsupported_capabilities_are_requested() -> None:
    """Multiple unsupported capabilities should all be mentioned in the reject reason."""
    inbound = build_task_create_message(["docs.search", "docs.translate", "docs.classify"])

    decision = evaluate_task_create(inbound)

    assert isinstance(decision, TaskRejectMessage)
    assert "docs.translate" in decision.payload.reason
    assert "docs.classify" in decision.payload.reason


def test_response_envelope_preserves_task_run_and_trace_ids() -> None:
    """Response envelope should preserve the correlated task/run/trace values."""
    inbound = build_task_create_message(["docs.search"])

    decision = evaluate_task_create(inbound)

    assert decision.envelope.task_id == inbound.envelope.task_id
    assert decision.envelope.run_id == inbound.envelope.run_id
    assert decision.envelope.trace_id == inbound.envelope.trace_id


def test_response_envelope_sets_sender_recipient_and_message_type_correctly() -> None:
    """Response envelope should set participant routing and the correct decision type."""
    inbound = build_task_create_message(["docs.search", "docs.unsupported"])

    decision = evaluate_task_create(inbound)

    assert decision.envelope.sender_id == "participant_docs"
    assert decision.envelope.recipient_id == inbound.envelope.sender_id
    assert decision.envelope.domain_id == "participant_docs"
    assert decision.envelope.message_type == MessageType.FAP_TASK_REJECT

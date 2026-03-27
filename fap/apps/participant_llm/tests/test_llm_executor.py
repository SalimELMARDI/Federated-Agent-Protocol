"""Tests for the participant_llm LLM-backed execution service."""

from __future__ import annotations

from pytest import MonkeyPatch

from fap_core.clocks import utc_now
from fap_core.enums import MessageType, PrivacyClass, SharingMode
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import GovernanceMetadata, MessageEnvelope, TaskCreateMessage, TaskCreatePayload
from participant_llm.adapters.llm_client import LLMCallError, LLMResponse
from participant_llm.service.executor import VOTE_ONLY_SUMMARY, execute_task_create

STUB_MODEL = "stub-model-v1"
STUB_ENDPOINT = "https://stub.example.com/v1/messages"
STUB_LLM_CONTENT = "Privacy policies should restrict data sharing to minimum necessary."


def _stub_call_llm(query: str) -> LLMResponse:
    """Return a canned LLM response for tests."""
    del query
    return LLMResponse(content=STUB_LLM_CONTENT, model=STUB_MODEL, endpoint_url=STUB_ENDPOINT)


def _stub_call_llm_error(query: str) -> LLMResponse:
    """Always raise LLMCallError — simulates a failed API call."""
    del query
    raise LLMCallError("API key is missing")


def build_task_create_message(
    *,
    input_query: str,
    governance: GovernanceMetadata | None = None,
) -> TaskCreateMessage:
    """Return a valid task-create message for execution tests."""
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
            governance=governance,
        ),
        payload=TaskCreatePayload(
            title="LLM query",
            description="Ask the LLM a governed question.",
            requested_capabilities=["llm.query"],
            input_query=input_query,
        ),
    )


def test_execution_returns_task_complete_policy_attest_and_aggregate_submit(
    monkeypatch: MonkeyPatch,
) -> None:
    """Execution should return canonical task-complete, policy-attest, and aggregate-submit."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_call_llm)

    result = execute_task_create(build_task_create_message(input_query="privacy"))

    assert result.task_complete_message.envelope.message_type == MessageType.FAP_TASK_COMPLETE
    assert result.policy_attest_message.envelope.message_type == MessageType.FAP_POLICY_ATTEST
    assert result.aggregate_submit_message.envelope.message_type == MessageType.FAP_AGGREGATE_SUBMIT


def test_execution_source_refs_carry_model_name_and_endpoint(
    monkeypatch: MonkeyPatch,
) -> None:
    """Source refs should identify the model and endpoint used for the response."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_call_llm)

    result = execute_task_create(build_task_create_message(input_query="privacy"))

    assert len(result.task_complete_message.payload.source_refs) == 1
    ref = result.task_complete_message.payload.source_refs[0]
    assert ref.participant_id == "participant_llm"
    assert ref.source_id == STUB_MODEL
    assert ref.source_title == f"LLM: {STUB_MODEL}"
    assert ref.source_path == STUB_ENDPOINT
    assert (
        result.aggregate_submit_message.payload.source_refs
        == result.task_complete_message.payload.source_refs
    )


def test_default_governance_applies_summary_only_to_internal_content(
    monkeypatch: MonkeyPatch,
) -> None:
    """Missing governance should default to INTERNAL + SUMMARY_ONLY → summary prefix."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_call_llm)

    result = execute_task_create(build_task_create_message(input_query="privacy"))

    assert result.policy_attest_message.payload.original_privacy_class == PrivacyClass.INTERNAL
    assert result.policy_attest_message.payload.applied_sharing_mode == SharingMode.SUMMARY_ONLY
    assert result.task_complete_message.payload.summary.startswith("[SUMMARY ONLY]")


def test_public_raw_governance_returns_raw_llm_content(
    monkeypatch: MonkeyPatch,
) -> None:
    """PUBLIC + RAW governance should export the LLM response unchanged."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_call_llm)

    result = execute_task_create(
        build_task_create_message(
            input_query="privacy",
            governance=GovernanceMetadata(
                privacy_class=PrivacyClass.PUBLIC,
                sharing_mode=SharingMode.RAW,
                policy_ref="policy.llm.v0",
            ),
        )
    )

    assert result.task_complete_message.payload.summary == STUB_LLM_CONTENT


def test_restricted_governance_returns_vote_only_summary(
    monkeypatch: MonkeyPatch,
) -> None:
    """RESTRICTED governance should collapse to vote-only output."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_call_llm)

    result = execute_task_create(
        build_task_create_message(
            input_query="privacy",
            governance=GovernanceMetadata(
                privacy_class=PrivacyClass.RESTRICTED,
                sharing_mode=SharingMode.SUMMARY_ONLY,
                policy_ref="policy.llm.v0",
            ),
        )
    )

    assert result.task_complete_message.payload.summary == VOTE_ONLY_SUMMARY


def test_failed_llm_call_returns_error_summary_with_empty_source_refs(
    monkeypatch: MonkeyPatch,
) -> None:
    """A failed LLM call should produce an error summary with no source refs."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_call_llm_error)

    result = execute_task_create(build_task_create_message(input_query="privacy"))

    assert "LLM query failed" in result.task_complete_message.payload.summary
    assert result.task_complete_message.payload.source_refs == []
    assert result.aggregate_submit_message.payload.source_refs == []


def test_result_envelope_preserves_task_run_and_trace_ids(
    monkeypatch: MonkeyPatch,
) -> None:
    """All three result messages should preserve correlated task, run, and trace ids."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_call_llm)
    inbound = build_task_create_message(input_query="privacy")

    result = execute_task_create(inbound)

    assert result.task_complete_message.envelope.task_id == inbound.envelope.task_id
    assert result.task_complete_message.envelope.run_id == inbound.envelope.run_id
    assert result.task_complete_message.envelope.trace_id == inbound.envelope.trace_id
    assert result.policy_attest_message.envelope.task_id == inbound.envelope.task_id
    assert result.policy_attest_message.envelope.run_id == inbound.envelope.run_id
    assert result.policy_attest_message.envelope.trace_id == inbound.envelope.trace_id
    assert result.aggregate_submit_message.envelope.task_id == inbound.envelope.task_id
    assert result.aggregate_submit_message.envelope.run_id == inbound.envelope.run_id
    assert result.aggregate_submit_message.envelope.trace_id == inbound.envelope.trace_id


def test_result_envelope_sets_sender_recipient_and_message_types_correctly(
    monkeypatch: MonkeyPatch,
) -> None:
    """All result messages should have correct participant routing and message types."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_call_llm)
    inbound = build_task_create_message(input_query="privacy")

    result = execute_task_create(inbound)

    assert result.task_complete_message.envelope.sender_id == "participant_llm"
    assert result.task_complete_message.envelope.recipient_id == inbound.envelope.sender_id
    assert result.task_complete_message.envelope.domain_id == "participant_llm"
    assert result.task_complete_message.envelope.message_type == MessageType.FAP_TASK_COMPLETE
    assert result.policy_attest_message.envelope.sender_id == "participant_llm"
    assert result.policy_attest_message.envelope.recipient_id == inbound.envelope.sender_id
    assert result.policy_attest_message.envelope.domain_id == "participant_llm"
    assert result.policy_attest_message.envelope.message_type == MessageType.FAP_POLICY_ATTEST
    assert result.aggregate_submit_message.envelope.sender_id == "participant_llm"
    assert result.aggregate_submit_message.envelope.recipient_id == inbound.envelope.sender_id
    assert result.aggregate_submit_message.envelope.domain_id == "participant_llm"
    assert result.aggregate_submit_message.envelope.message_type == MessageType.FAP_AGGREGATE_SUBMIT
    assert (
        result.aggregate_submit_message.payload.provenance_ref
        == result.policy_attest_message.envelope.message_id
    )
    assert (
        result.aggregate_submit_message.payload.summary
        == result.task_complete_message.payload.summary
    )

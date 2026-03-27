"""Unit tests for participant_llm execution — policy paths, source refs, and error handling.

The LLM adapter is monkeypatched so no real API calls are made.  Tests cover:
- the full policy rule matrix (PUBLIC/RAW, INTERNAL/SUMMARY_ONLY, RESTRICTED)
- graceful degradation when the LLM call fails
- source ref construction from LLM response metadata
- the provenance chain between policy_attest and aggregate_submit
- cross-message consistency guarantees required by the FAP spec
"""

from __future__ import annotations

from pytest import MonkeyPatch

from fap_core.clocks import utc_now
from fap_core.enums import MessageType, PrivacyClass, SharingMode
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import GovernanceMetadata, MessageEnvelope, TaskCreateMessage, TaskCreatePayload
from participant_llm.adapters.llm_client import LLMCallError, LLMResponse
from participant_llm.service.executor import VOTE_ONLY_SUMMARY, execute_task_create

STUB_MODEL = "stub-model-v0"
STUB_ENDPOINT = "https://stub.example.com/v1/messages"
STUB_CONTENT = "Data minimisation limits what the model can retain across sessions."


def _stub_llm(query: str) -> LLMResponse:
    del query
    return LLMResponse(content=STUB_CONTENT, model=STUB_MODEL, endpoint_url=STUB_ENDPOINT)


def _stub_llm_error(query: str) -> LLMResponse:
    del query
    raise LLMCallError("connection refused")


def _build_message(
    *,
    input_query: str = "privacy",
    governance: GovernanceMetadata | None = None,
) -> TaskCreateMessage:
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
            governance=governance,
        ),
        payload=TaskCreatePayload(
            title="LLM query",
            description="Query the LLM.",
            requested_capabilities=["llm.query"],
            input_query=input_query,
        ),
    )


# ---------------------------------------------------------------------------
# Policy paths
# ---------------------------------------------------------------------------


def test_default_governance_applies_summary_only_prefix(monkeypatch: MonkeyPatch) -> None:
    """INTERNAL + SUMMARY_ONLY (defaults) must prefix the export with [SUMMARY ONLY]."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)

    result = execute_task_create(_build_message())

    assert result.task_complete_message.payload.summary.startswith("[SUMMARY ONLY]")
    assert STUB_CONTENT in result.task_complete_message.payload.summary


def test_default_governance_records_internal_privacy_class(monkeypatch: MonkeyPatch) -> None:
    """The policy-attest payload must record PrivacyClass.INTERNAL for the default governance."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)

    result = execute_task_create(_build_message())

    assert result.policy_attest_message.payload.original_privacy_class == PrivacyClass.INTERNAL
    assert result.policy_attest_message.payload.applied_sharing_mode == SharingMode.SUMMARY_ONLY


def test_public_raw_governance_exports_content_unchanged(monkeypatch: MonkeyPatch) -> None:
    """PUBLIC + RAW governance must return the raw LLM content without transformation."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)

    result = execute_task_create(
        _build_message(
            governance=GovernanceMetadata(
                privacy_class=PrivacyClass.PUBLIC,
                sharing_mode=SharingMode.RAW,
                policy_ref="policy.llm.v0",
            )
        )
    )

    assert result.task_complete_message.payload.summary == STUB_CONTENT


def test_restricted_governance_collapses_to_vote_only(monkeypatch: MonkeyPatch) -> None:
    """RESTRICTED governance must suppress content and return the vote-only constant."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)

    result = execute_task_create(
        _build_message(
            governance=GovernanceMetadata(
                privacy_class=PrivacyClass.RESTRICTED,
                sharing_mode=SharingMode.SUMMARY_ONLY,
                policy_ref="policy.llm.v0",
            )
        )
    )

    assert result.task_complete_message.payload.summary == VOTE_ONLY_SUMMARY


def test_sensitive_raw_request_is_downgraded_to_summary_only(monkeypatch: MonkeyPatch) -> None:
    """SENSITIVE + RAW must be downgraded to SUMMARY_ONLY by the policy engine."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)

    result = execute_task_create(
        _build_message(
            governance=GovernanceMetadata(
                privacy_class=PrivacyClass.SENSITIVE,
                sharing_mode=SharingMode.RAW,
                policy_ref="policy.llm.v0",
            )
        )
    )

    assert result.task_complete_message.payload.summary.startswith("[SUMMARY ONLY]")
    assert result.policy_attest_message.payload.applied_sharing_mode == SharingMode.SUMMARY_ONLY


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_llm_failure_produces_error_summary(monkeypatch: MonkeyPatch) -> None:
    """A failed LLM call must produce a summary that describes the error."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm_error)

    result = execute_task_create(_build_message())

    assert "LLM query failed" in result.task_complete_message.payload.summary


def test_llm_failure_produces_empty_source_refs(monkeypatch: MonkeyPatch) -> None:
    """A failed LLM call must produce empty source_refs on both output messages."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm_error)

    result = execute_task_create(_build_message())

    assert result.task_complete_message.payload.source_refs == []
    assert result.aggregate_submit_message.payload.source_refs == []


def test_llm_failure_still_produces_valid_three_message_bundle(monkeypatch: MonkeyPatch) -> None:
    """Even on LLM failure the executor must return all three canonical messages."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm_error)

    result = execute_task_create(_build_message())

    assert result.task_complete_message.envelope.message_type == MessageType.FAP_TASK_COMPLETE
    assert result.policy_attest_message.envelope.message_type == MessageType.FAP_POLICY_ATTEST
    assert result.aggregate_submit_message.envelope.message_type == MessageType.FAP_AGGREGATE_SUBMIT


# ---------------------------------------------------------------------------
# Source refs
# ---------------------------------------------------------------------------


def test_source_ref_carries_model_name_as_source_id(monkeypatch: MonkeyPatch) -> None:
    """source_ref.source_id must match the model name returned by the LLM adapter."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)

    result = execute_task_create(_build_message())

    assert len(result.task_complete_message.payload.source_refs) == 1
    assert result.task_complete_message.payload.source_refs[0].source_id == STUB_MODEL


def test_source_ref_carries_endpoint_as_source_path(monkeypatch: MonkeyPatch) -> None:
    """source_ref.source_path must match the endpoint URL returned by the LLM adapter."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)

    result = execute_task_create(_build_message())

    assert result.task_complete_message.payload.source_refs[0].source_path == STUB_ENDPOINT


def test_source_ref_title_includes_model_name(monkeypatch: MonkeyPatch) -> None:
    """source_ref.source_title must be 'LLM: {model}'."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)

    result = execute_task_create(_build_message())

    assert result.task_complete_message.payload.source_refs[0].source_title == f"LLM: {STUB_MODEL}"


def test_source_refs_are_identical_on_task_complete_and_aggregate_submit(
    monkeypatch: MonkeyPatch,
) -> None:
    """task_complete and aggregate_submit must carry the same source_refs."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)

    result = execute_task_create(_build_message())

    assert (
        result.aggregate_submit_message.payload.source_refs
        == result.task_complete_message.payload.source_refs
    )


# ---------------------------------------------------------------------------
# Provenance chain and cross-message consistency
# ---------------------------------------------------------------------------


def test_aggregate_submit_provenance_ref_links_to_policy_attest(
    monkeypatch: MonkeyPatch,
) -> None:
    """aggregate_submit.provenance_ref must equal policy_attest.envelope.message_id."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)

    result = execute_task_create(_build_message())

    assert (
        result.aggregate_submit_message.payload.provenance_ref
        == result.policy_attest_message.envelope.message_id
    )


def test_aggregate_submit_summary_matches_task_complete_summary(
    monkeypatch: MonkeyPatch,
) -> None:
    """aggregate_submit.summary must be identical to task_complete.summary."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)

    result = execute_task_create(_build_message())

    assert (
        result.aggregate_submit_message.payload.summary
        == result.task_complete_message.payload.summary
    )


def test_all_messages_carry_same_task_run_and_trace_ids(monkeypatch: MonkeyPatch) -> None:
    """All three result messages must mirror the inbound task_id, run_id, and trace_id."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    inbound = _build_message()

    result = execute_task_create(inbound)

    for msg in (
        result.task_complete_message,
        result.policy_attest_message,
        result.aggregate_submit_message,
    ):
        assert msg.envelope.task_id == inbound.envelope.task_id
        assert msg.envelope.run_id == inbound.envelope.run_id
        assert msg.envelope.trace_id == inbound.envelope.trace_id

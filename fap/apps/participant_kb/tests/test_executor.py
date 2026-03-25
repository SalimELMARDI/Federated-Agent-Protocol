"""Tests for the participant_kb deterministic execution service."""

from __future__ import annotations

from pathlib import Path

from pytest import MonkeyPatch

from fap_core.clocks import utc_now
from fap_core.enums import MessageType, PrivacyClass, SharingMode
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import GovernanceMetadata, MessageEnvelope, TaskCreateMessage, TaskCreatePayload
from participant_kb.config import KB_PATH_ENV_VAR
from participant_kb.service.executor import VOTE_ONLY_SUMMARY, execute_task_create


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
            recipient_id="participant_kb",
            domain_id="kb",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
            governance=governance,
        ),
        payload=TaskCreatePayload(
            title="Query local KB",
            description="Perform a deterministic local KB search.",
            requested_capabilities=["kb.lookup"],
            input_query=input_query,
        ),
    )


def test_execution_with_matching_entries_returns_task_complete_policy_attest_and_aggregate_submit() -> None:
    """Execution should return canonical task-complete, policy-attest, and aggregate-submit messages."""
    result = execute_task_create(build_task_create_message(input_query="privacy"))

    assert result.task_complete_message.envelope.message_type == MessageType.FAP_TASK_COMPLETE
    assert result.policy_attest_message.envelope.message_type == MessageType.FAP_POLICY_ATTEST
    assert result.aggregate_submit_message.envelope.message_type == MessageType.FAP_AGGREGATE_SUBMIT
    assert "Privacy controls" in result.task_complete_message.payload.summary
    assert result.task_complete_message.payload.source_refs[0].participant_id == "participant_kb"
    assert result.task_complete_message.payload.source_refs[0].source_id == "kb-001"
    assert result.task_complete_message.payload.source_refs[0].source_title == "Privacy controls"
    assert result.task_complete_message.payload.source_refs[0].source_path.endswith(
        "kb-001__privacy-controls.json"
    )
    assert (
        result.aggregate_submit_message.payload.source_refs
        == result.task_complete_message.payload.source_refs
    )


def test_default_governance_uses_internal_and_summary_only() -> None:
    """Missing governance should fall back to the default policy inputs."""
    result = execute_task_create(build_task_create_message(input_query="privacy"))

    assert result.policy_attest_message.payload.original_privacy_class == PrivacyClass.INTERNAL
    assert result.policy_attest_message.payload.applied_sharing_mode == SharingMode.SUMMARY_ONLY


def test_public_raw_returns_raw_unchanged_content() -> None:
    """Public raw requests should keep the local content unchanged."""
    result = execute_task_create(
        build_task_create_message(
            input_query="privacy",
            governance=GovernanceMetadata(
                privacy_class=PrivacyClass.PUBLIC,
                sharing_mode=SharingMode.RAW,
                policy_ref="policy.kb.v0",
            ),
        )
    )

    assert result.task_complete_message.payload.summary == "Matched KB entries: Privacy controls"


def test_internal_raw_returns_redacted_content() -> None:
    """Internal raw requests should be downgraded to redacted content."""
    result = execute_task_create(
        build_task_create_message(
            input_query="privacy",
            governance=GovernanceMetadata(
                privacy_class=PrivacyClass.INTERNAL,
                sharing_mode=SharingMode.RAW,
                policy_ref="policy.kb.v0",
            ),
        )
    )

    assert (
        result.task_complete_message.payload.summary
        == "[REDACTED EXPORT] Matched KB entries: Privacy controls"
    )


def test_restricted_summary_only_returns_vote_only_summary() -> None:
    """Restricted summary-only requests should collapse to vote-only output."""
    result = execute_task_create(
        build_task_create_message(
            input_query="privacy",
            governance=GovernanceMetadata(
                privacy_class=PrivacyClass.RESTRICTED,
                sharing_mode=SharingMode.SUMMARY_ONLY,
                policy_ref="policy.kb.v0",
            ),
        )
    )

    assert result.task_complete_message.payload.summary == VOTE_ONLY_SUMMARY


def test_result_envelope_preserves_task_run_and_trace_ids() -> None:
    """Task-complete responses should preserve correlated task, run, and trace ids."""
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


def test_result_envelope_sets_sender_recipient_and_message_type_correctly() -> None:
    """Task-complete responses should set participant routing and message type correctly."""
    inbound = build_task_create_message(input_query="privacy")

    result = execute_task_create(inbound)

    assert result.task_complete_message.envelope.sender_id == "participant_kb"
    assert result.task_complete_message.envelope.recipient_id == inbound.envelope.sender_id
    assert result.task_complete_message.envelope.domain_id == "participant_kb"
    assert result.task_complete_message.envelope.message_type == MessageType.FAP_TASK_COMPLETE
    assert result.policy_attest_message.envelope.sender_id == "participant_kb"
    assert result.policy_attest_message.envelope.recipient_id == inbound.envelope.sender_id
    assert result.policy_attest_message.envelope.domain_id == "participant_kb"
    assert result.policy_attest_message.envelope.message_type == MessageType.FAP_POLICY_ATTEST
    assert result.aggregate_submit_message.envelope.sender_id == "participant_kb"
    assert result.aggregate_submit_message.envelope.recipient_id == inbound.envelope.sender_id
    assert result.aggregate_submit_message.envelope.domain_id == "participant_kb"
    assert result.aggregate_submit_message.envelope.message_type == MessageType.FAP_AGGREGATE_SUBMIT
    assert (
        result.aggregate_submit_message.payload.provenance_ref
        == result.policy_attest_message.envelope.message_id
    )
    assert (
        result.aggregate_submit_message.payload.summary
        == result.task_complete_message.payload.summary
    )


def test_execution_uses_loaded_local_kb_content(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Execution should read the configured file-backed KB connector."""
    (tmp_path / "kb-900__release-roadmap.txt").write_text(
        "Roadmap guidance for staged release reviews.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(KB_PATH_ENV_VAR, str(tmp_path))

    result = execute_task_create(build_task_create_message(input_query="roadmap"))

    assert result.task_complete_message.payload.summary == (
        "[SUMMARY ONLY] Matched KB entries: Release Roadmap"
    )


def test_execution_with_no_matching_entries_returns_empty_source_refs() -> None:
    """No-match execution should emit no source refs."""
    result = execute_task_create(build_task_create_message(input_query="definitely-no-kb-match"))

    assert result.task_complete_message.payload.source_refs == []
    assert result.aggregate_submit_message.payload.source_refs == []

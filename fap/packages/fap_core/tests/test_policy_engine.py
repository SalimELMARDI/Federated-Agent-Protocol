"""Tests for the shared executable FAP policy engine."""

from __future__ import annotations

import pytest

from fap_core.enums import MessageType, PolicyTransformType, PrivacyClass, SharingMode
from fap_core.ids import new_run_id, new_task_id, new_trace_id
from fap_core.policy import LocalResult, PolicyEnvelopeContext, apply_policy


def build_local_result(
    *,
    privacy_class: PrivacyClass,
    requested_sharing_mode: SharingMode,
    content: str = "Sensitive incident notes.",
) -> LocalResult:
    """Return a valid local result for policy-engine tests."""
    return LocalResult(
        participant_id="participant_docs",
        content=content,
        privacy_class=privacy_class,
        requested_sharing_mode=requested_sharing_mode,
    )


def test_public_raw_stays_raw_with_unchanged_content() -> None:
    """Public raw exports should pass through unchanged."""
    decision = apply_policy(
        build_local_result(
            privacy_class=PrivacyClass.PUBLIC,
            requested_sharing_mode=SharingMode.RAW,
            content="Public release note.",
        ),
        policy_ref="policy.docs.v0",
    )

    assert decision.approved_export.sharing_mode == SharingMode.RAW
    assert decision.approved_export.content == "Public release note."
    assert decision.approved_export.redactions_applied is False


def test_internal_raw_becomes_redacted_with_prefix() -> None:
    """Internal raw exports should be downgraded to redacted."""
    decision = apply_policy(
        build_local_result(
            privacy_class=PrivacyClass.INTERNAL,
            requested_sharing_mode=SharingMode.RAW,
        ),
        policy_ref="policy.docs.v0",
    )

    assert decision.approved_export.sharing_mode == SharingMode.REDACTED
    assert decision.approved_export.content == "[REDACTED EXPORT] Sensitive incident notes."
    assert decision.approved_export.redactions_applied is True


def test_sensitive_redacted_becomes_summary_only() -> None:
    """Sensitive redacted requests should downgrade to summary-only."""
    decision = apply_policy(
        build_local_result(
            privacy_class=PrivacyClass.SENSITIVE,
            requested_sharing_mode=SharingMode.REDACTED,
        ),
        policy_ref="policy.docs.v0",
    )

    assert decision.approved_export.sharing_mode == SharingMode.SUMMARY_ONLY
    assert decision.approved_export.content == "[SUMMARY ONLY] Sensitive incident notes."
    assert decision.approved_export.redactions_applied is False


def test_restricted_summary_only_becomes_vote_only_with_no_content() -> None:
    """Restricted summary-only requests should downgrade to vote-only."""
    decision = apply_policy(
        build_local_result(
            privacy_class=PrivacyClass.RESTRICTED,
            requested_sharing_mode=SharingMode.SUMMARY_ONLY,
        ),
        policy_ref="policy.docs.v0",
    )

    assert decision.approved_export.sharing_mode == SharingMode.VOTE_ONLY
    assert decision.approved_export.content is None
    assert decision.approved_export.redactions_applied is False


@pytest.mark.parametrize(
    ("privacy_class",),
    [
        (PrivacyClass.PUBLIC,),
        (PrivacyClass.INTERNAL,),
        (PrivacyClass.SENSITIVE,),
        (PrivacyClass.RESTRICTED,),
    ],
)
def test_vote_only_always_returns_no_content(privacy_class: PrivacyClass) -> None:
    """Vote-only requests should never export content regardless of privacy class."""
    decision = apply_policy(
        build_local_result(
            privacy_class=privacy_class,
            requested_sharing_mode=SharingMode.VOTE_ONLY,
        ),
        policy_ref="policy.docs.v0",
    )

    assert decision.approved_export.sharing_mode == SharingMode.VOTE_ONLY
    assert decision.approved_export.content is None
    assert decision.approved_export.redactions_applied is False


def test_policy_attestation_uses_canonical_message_type_and_payload() -> None:
    """Applying policy should always emit a canonical policy attestation message."""
    decision = apply_policy(
        build_local_result(
            privacy_class=PrivacyClass.INTERNAL,
            requested_sharing_mode=SharingMode.RAW,
        ),
        policy_ref="policy.docs.v0",
    )

    message = decision.policy_attest_message
    assert message.envelope.message_type == MessageType.FAP_POLICY_ATTEST
    assert message.envelope.sender_id == "participant_docs"
    assert message.envelope.recipient_id == "coordinator"
    assert message.envelope.domain_id == "participant_docs"
    assert message.payload.participant_id == "participant_docs"
    assert message.payload.policy_ref == "policy.docs.v0"
    assert message.payload.original_privacy_class == PrivacyClass.INTERNAL
    assert message.payload.applied_sharing_mode == SharingMode.REDACTED
    assert message.payload.transform_type == PolicyTransformType.REDACTED


def test_apply_policy_without_envelope_context_still_works() -> None:
    """Standalone policy application should still emit a valid attestation."""
    decision = apply_policy(
        build_local_result(
            privacy_class=PrivacyClass.PUBLIC,
            requested_sharing_mode=SharingMode.RAW,
        ),
        policy_ref="policy.docs.v0",
    )

    assert decision.policy_attest_message.envelope.message_type == MessageType.FAP_POLICY_ATTEST
    assert decision.policy_attest_message.envelope.sender_id == "participant_docs"
    assert decision.policy_attest_message.envelope.recipient_id == "coordinator"
    assert decision.policy_attest_message.envelope.domain_id == "participant_docs"


def test_apply_policy_with_envelope_context_preserves_run_correlation_fields() -> None:
    """Envelope context should be carried through to the generated attestation."""
    envelope_context = PolicyEnvelopeContext(
        task_id=new_task_id(),
        run_id=new_run_id(),
        trace_id=new_trace_id(),
        recipient_id="coordinator",
        sender_id="participant_docs",
        domain_id="participant_docs",
    )

    decision = apply_policy(
        build_local_result(
            privacy_class=PrivacyClass.INTERNAL,
            requested_sharing_mode=SharingMode.RAW,
        ),
        policy_ref="policy.docs.v0",
        envelope_context=envelope_context,
    )

    message = decision.policy_attest_message
    assert message.envelope.task_id == envelope_context.task_id
    assert message.envelope.run_id == envelope_context.run_id
    assert message.envelope.trace_id == envelope_context.trace_id
    assert message.envelope.recipient_id == envelope_context.recipient_id
    assert message.envelope.sender_id == envelope_context.sender_id
    assert message.envelope.domain_id == envelope_context.domain_id
    assert message.envelope.message_type == MessageType.FAP_POLICY_ATTEST


def test_apply_policy_with_envelope_context_still_generates_fresh_message_ids() -> None:
    """Attestation message ids should remain fresh even when context is provided."""
    envelope_context = PolicyEnvelopeContext(
        task_id=new_task_id(),
        run_id=new_run_id(),
        trace_id=new_trace_id(),
        recipient_id="coordinator",
        sender_id="participant_docs",
        domain_id="participant_docs",
    )

    first = apply_policy(
        build_local_result(
            privacy_class=PrivacyClass.INTERNAL,
            requested_sharing_mode=SharingMode.SUMMARY_ONLY,
        ),
        policy_ref="policy.docs.v0",
        envelope_context=envelope_context,
    )
    second = apply_policy(
        build_local_result(
            privacy_class=PrivacyClass.INTERNAL,
            requested_sharing_mode=SharingMode.SUMMARY_ONLY,
        ),
        policy_ref="policy.docs.v0",
        envelope_context=envelope_context,
    )

    assert first.policy_attest_message.envelope.message_id.startswith("msg_")
    assert second.policy_attest_message.envelope.message_id.startswith("msg_")
    assert first.policy_attest_message.envelope.message_id != second.policy_attest_message.envelope.message_id


def test_attestation_applied_sharing_mode_matches_actual_export_mode() -> None:
    """Attestations should reflect the actual export mode used by policy."""
    decision = apply_policy(
        build_local_result(
            privacy_class=PrivacyClass.RESTRICTED,
            requested_sharing_mode=SharingMode.RAW,
        ),
        policy_ref="policy.docs.v0",
    )

    assert (
        decision.policy_attest_message.payload.applied_sharing_mode
        == decision.approved_export.sharing_mode
    )
    assert decision.policy_attest_message.payload.transform_type == PolicyTransformType.VOTE_ONLY

"""Deterministic shared policy engine for FAP v0.1."""

from __future__ import annotations

from fap_core.clocks import utc_now
from fap_core.enums import MessageType, PolicyTransformType, PrivacyClass, SharingMode
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import MessageEnvelope, PolicyAttestMessage, PolicyAttestPayload
from fap_core.policy.models import (
    ApprovedExport,
    LocalResult,
    PolicyDecision,
    PolicyEnvelopeContext,
)

POLICY_RULES: dict[PrivacyClass, dict[SharingMode, SharingMode]] = {
    PrivacyClass.PUBLIC: {
        SharingMode.RAW: SharingMode.RAW,
        SharingMode.REDACTED: SharingMode.REDACTED,
        SharingMode.SUMMARY_ONLY: SharingMode.SUMMARY_ONLY,
        SharingMode.VOTE_ONLY: SharingMode.VOTE_ONLY,
    },
    PrivacyClass.INTERNAL: {
        SharingMode.RAW: SharingMode.REDACTED,
        SharingMode.REDACTED: SharingMode.REDACTED,
        SharingMode.SUMMARY_ONLY: SharingMode.SUMMARY_ONLY,
        SharingMode.VOTE_ONLY: SharingMode.VOTE_ONLY,
    },
    PrivacyClass.SENSITIVE: {
        SharingMode.RAW: SharingMode.SUMMARY_ONLY,
        SharingMode.REDACTED: SharingMode.SUMMARY_ONLY,
        SharingMode.SUMMARY_ONLY: SharingMode.SUMMARY_ONLY,
        SharingMode.VOTE_ONLY: SharingMode.VOTE_ONLY,
    },
    PrivacyClass.RESTRICTED: {
        SharingMode.RAW: SharingMode.VOTE_ONLY,
        SharingMode.REDACTED: SharingMode.VOTE_ONLY,
        SharingMode.SUMMARY_ONLY: SharingMode.VOTE_ONLY,
        SharingMode.VOTE_ONLY: SharingMode.VOTE_ONLY,
    },
}


def apply_policy(
    local_result: LocalResult,
    *,
    policy_ref: str,
    envelope_context: PolicyEnvelopeContext | None = None,
) -> PolicyDecision:
    """Apply the v0.1 policy rules to a local result and build an attestation."""
    normalized_policy_ref = policy_ref.strip()
    if not normalized_policy_ref:
        raise ValueError("policy_ref must not be blank")

    applied_sharing_mode = POLICY_RULES[local_result.privacy_class][
        local_result.requested_sharing_mode
    ]
    approved_export = _build_approved_export(local_result, applied_sharing_mode)
    policy_attest_message = _build_policy_attest_message(
        local_result=local_result,
        policy_ref=normalized_policy_ref,
        applied_sharing_mode=applied_sharing_mode,
        envelope_context=envelope_context,
    )

    return PolicyDecision(
        approved_export=approved_export,
        policy_attest_message=policy_attest_message,
    )


def _build_approved_export(
    local_result: LocalResult, applied_sharing_mode: SharingMode
) -> ApprovedExport:
    """Return the canonical export produced by the applied policy rule."""
    if applied_sharing_mode == SharingMode.RAW:
        return ApprovedExport(
            content=local_result.content,
            sharing_mode=SharingMode.RAW,
            redactions_applied=False,
        )

    if applied_sharing_mode == SharingMode.REDACTED:
        if (
            local_result.privacy_class == PrivacyClass.PUBLIC
            and local_result.requested_sharing_mode == SharingMode.REDACTED
        ):
            return ApprovedExport(
                content=local_result.content,
                sharing_mode=SharingMode.REDACTED,
                redactions_applied=False,
            )

        return ApprovedExport(
            content=f"[REDACTED EXPORT] {local_result.content}",
            sharing_mode=SharingMode.REDACTED,
            redactions_applied=True,
        )

    if applied_sharing_mode == SharingMode.SUMMARY_ONLY:
        return ApprovedExport(
            content=f"[SUMMARY ONLY] {local_result.content}",
            sharing_mode=SharingMode.SUMMARY_ONLY,
            redactions_applied=False,
        )

    return ApprovedExport(
        content=None,
        sharing_mode=SharingMode.VOTE_ONLY,
        redactions_applied=False,
    )


def _build_policy_attest_message(
    *,
    local_result: LocalResult,
    policy_ref: str,
    applied_sharing_mode: SharingMode,
    envelope_context: PolicyEnvelopeContext | None,
) -> PolicyAttestMessage:
    """Build the canonical policy attestation for an applied export decision."""
    attestation_note: str | None = None
    if applied_sharing_mode != local_result.requested_sharing_mode:
        attestation_note = (
            "Requested sharing mode "
            f"{local_result.requested_sharing_mode.value!r} "
            f"downgraded to {applied_sharing_mode.value!r}."
        )

    if envelope_context is None:
        task_id = new_task_id()
        run_id = new_run_id()
        trace_id = new_trace_id()
        sender_id = local_result.participant_id
        recipient_id = "coordinator"
        domain_id = local_result.participant_id
    else:
        task_id = envelope_context.task_id
        run_id = envelope_context.run_id
        trace_id = envelope_context.trace_id
        sender_id = envelope_context.sender_id
        recipient_id = envelope_context.recipient_id
        domain_id = envelope_context.domain_id

    return PolicyAttestMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_POLICY_ATTEST,
            task_id=task_id,
            run_id=run_id,
            message_id=new_message_id(),
            sender_id=sender_id,
            recipient_id=recipient_id,
            domain_id=domain_id,
            trace_id=trace_id,
            timestamp=utc_now(),
        ),
        payload=PolicyAttestPayload(
            participant_id=local_result.participant_id,
            policy_ref=policy_ref,
            original_privacy_class=local_result.privacy_class,
            applied_sharing_mode=applied_sharing_mode,
            transform_type=PolicyTransformType(applied_sharing_mode.value),
            attestation_note=attestation_note,
        ),
    )

"""Tests for the policy attestation message model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fap_core.clocks import utc_now
from fap_core.enums import MessageType, PolicyTransformType, PrivacyClass, SharingMode
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import MessageEnvelope, PolicyAttestMessage, PolicyAttestPayload


def build_envelope(message_type: MessageType) -> MessageEnvelope:
    """Return a valid envelope for policy message tests."""
    return MessageEnvelope(
        message_type=message_type,
        task_id=new_task_id(),
        run_id=new_run_id(),
        message_id=new_message_id(),
        sender_id="participant_docs",
        recipient_id="coordinator",
        domain_id="docs",
        trace_id=new_trace_id(),
        timestamp=utc_now(),
    )


def test_policy_attest_message_accepts_valid_data() -> None:
    """A valid policy attestation message should parse cleanly."""
    message = PolicyAttestMessage(
        envelope=build_envelope(MessageType.FAP_POLICY_ATTEST),
        payload=PolicyAttestPayload(
            participant_id="participant_docs",
            policy_ref="policy/fap-v0.1",
            original_privacy_class=PrivacyClass.SENSITIVE,
            applied_sharing_mode=SharingMode.REDACTED,
            transform_type=PolicyTransformType.REDACTED,
            attestation_note="Names were removed before export.",
        ),
    )

    assert message.envelope.message_type == MessageType.FAP_POLICY_ATTEST
    assert message.payload.original_privacy_class == PrivacyClass.SENSITIVE
    assert message.payload.applied_sharing_mode == SharingMode.REDACTED
    assert message.payload.transform_type == PolicyTransformType.REDACTED


@pytest.mark.parametrize("field_name", ["participant_id", "policy_ref", "transform_type"])
def test_policy_attest_payload_rejects_blank_required_strings(field_name: str) -> None:
    """Required policy attestation strings should reject blank values."""
    payload: dict[str, object] = {
        "participant_id": "participant_docs",
        "policy_ref": "policy/fap-v0.1",
        "original_privacy_class": PrivacyClass.SENSITIVE,
        "applied_sharing_mode": SharingMode.REDACTED,
        "transform_type": "redacted",
    }
    payload[field_name] = "   "

    with pytest.raises(ValidationError):
        PolicyAttestPayload.model_validate(payload)


def test_policy_attest_payload_rejects_blank_attestation_note() -> None:
    """Optional attestation notes should reject blank strings."""
    with pytest.raises(ValidationError):
        PolicyAttestPayload(
            participant_id="participant_docs",
            policy_ref="policy/fap-v0.1",
            original_privacy_class=PrivacyClass.SENSITIVE,
            applied_sharing_mode=SharingMode.REDACTED,
            transform_type=PolicyTransformType.REDACTED,
            attestation_note="   ",
        )


def test_policy_attest_message_rejects_wrong_envelope_type() -> None:
    """Policy attest messages should enforce the matching envelope type."""
    with pytest.raises(ValidationError):
        PolicyAttestMessage(
            envelope=build_envelope(MessageType.FAP_TASK_COMPLETE),
            payload=PolicyAttestPayload(
                participant_id="participant_docs",
                policy_ref="policy/fap-v0.1",
                original_privacy_class=PrivacyClass.SENSITIVE,
                applied_sharing_mode=SharingMode.REDACTED,
                transform_type=PolicyTransformType.REDACTED,
            ),
        )

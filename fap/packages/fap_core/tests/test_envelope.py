"""Tests for the shared FAP message envelope."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from fap_core.clocks import utc_now
from fap_core.enums import MessageType, PrivacyClass, ProtocolVersion, SharingMode
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import GovernanceMetadata, MessageEnvelope


def test_message_envelope_accepts_valid_data() -> None:
    """A valid base envelope should parse cleanly."""
    envelope = MessageEnvelope(
        message_type=MessageType.FAP_TASK_CREATE,
        task_id=new_task_id(),
        run_id=new_run_id(),
        message_id=new_message_id(),
        sender_id="coordinator",
        recipient_id="participant_docs",
        domain_id="docs",
        trace_id=new_trace_id(),
        timestamp=utc_now(),
        governance=GovernanceMetadata(
            privacy_class=PrivacyClass.INTERNAL,
            sharing_mode=SharingMode.SUMMARY_ONLY,
            policy_ref="policy/v0.1",
            provenance_ref="prov/123",
        ),
    )

    assert envelope.protocol == "FAP"
    assert envelope.version == ProtocolVersion.V0_1
    assert envelope.message_type == MessageType.FAP_TASK_CREATE
    assert envelope.governance is not None
    assert envelope.governance.privacy_class == PrivacyClass.INTERNAL
    assert envelope.governance.sharing_mode == SharingMode.SUMMARY_ONLY


def test_message_envelope_rejects_invalid_protocol() -> None:
    """The envelope should reject non-FAP protocol markers."""
    with pytest.raises(ValidationError):
        MessageEnvelope(
            protocol="NOT_FAP",
            message_type=MessageType.FAP_TASK_CREATE,
            task_id=new_task_id(),
            run_id=new_run_id(),
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id="participant_docs",
            domain_id="docs",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
        )


def test_message_envelope_rejects_blank_task_id() -> None:
    """Task IDs should reject blank or whitespace-only values."""
    with pytest.raises(ValidationError):
        MessageEnvelope(
            message_type=MessageType.FAP_TASK_CREATE,
            task_id="   ",
            run_id=new_run_id(),
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id="participant_docs",
            domain_id="docs",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
        )


def test_message_envelope_rejects_naive_timestamp() -> None:
    """Timestamps must include timezone information."""
    with pytest.raises(ValidationError):
        MessageEnvelope(
            message_type=MessageType.FAP_TASK_CREATE,
            task_id=new_task_id(),
            run_id=new_run_id(),
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id="participant_docs",
            domain_id="docs",
            trace_id=new_trace_id(),
            timestamp=datetime(2026, 3, 21, 12, 0, 0),
        )


def test_governance_metadata_accepts_valid_values() -> None:
    """Governance metadata should parse valid privacy and sharing values."""
    governance = GovernanceMetadata.model_validate(
        {
            "privacy_class": "restricted",
            "sharing_mode": "redacted",
            "policy_ref": "policy/fap-v0.1",
            "provenance_ref": "provenance/abc",
        }
    )

    assert governance.privacy_class == PrivacyClass.RESTRICTED
    assert governance.sharing_mode == SharingMode.REDACTED

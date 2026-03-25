"""Tests for the participant_docs execution endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from fap_core import message_to_dict
from fap_core.clocks import utc_now
from fap_core.enums import MessageType, PrivacyClass, SharingMode
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import (
    ExceptionMessage,
    ExceptionPayload,
    GovernanceMetadata,
    MessageEnvelope,
    TaskCreateMessage,
    TaskCreatePayload,
)
from participant_docs.main import app

client = TestClient(app)


def build_envelope(
    message_type: MessageType,
    *,
    sender_id: str,
    recipient_id: str,
    governance: GovernanceMetadata | None = None,
) -> MessageEnvelope:
    """Return a valid envelope for participant_docs execute API tests."""
    return MessageEnvelope(
        message_type=message_type,
        task_id=new_task_id(),
        run_id=new_run_id(),
        message_id=new_message_id(),
        sender_id=sender_id,
        recipient_id=recipient_id,
        domain_id="docs",
        trace_id=new_trace_id(),
        timestamp=utc_now(),
        governance=governance,
    )


def build_task_create_message(
    *,
    input_query: str,
    governance: GovernanceMetadata | None = None,
) -> TaskCreateMessage:
    """Return a valid task-create message for execute endpoint tests."""
    return TaskCreateMessage(
        envelope=build_envelope(
            MessageType.FAP_TASK_CREATE,
            sender_id="coordinator",
            recipient_id="participant_docs",
            governance=governance,
        ),
        payload=TaskCreatePayload(
            title="Search local docs",
            description="Perform a deterministic local docs search.",
            requested_capabilities=["docs.search"],
            input_query=input_query,
        ),
    )


def build_exception_message() -> ExceptionMessage:
    """Return a valid exception message for negative execution tests."""
    return ExceptionMessage(
        envelope=build_envelope(
            MessageType.FAP_EXCEPTION,
            sender_id="coordinator",
            recipient_id="participant_docs",
        ),
        payload=ExceptionPayload(
            code="participant.unavailable",
            message="The participant could not access its local source.",
        ),
    )


def test_execute_endpoint_returns_three_canonical_messages_with_default_governance() -> None:
    """Default governance execution should return task-complete, policy-attest, and aggregate-submit messages."""
    inbound = build_task_create_message(input_query="privacy")

    response = client.post("/execute", json=message_to_dict(inbound))

    body = response.json()
    assert response.status_code == 200
    assert body["task_complete"]["envelope"]["message_type"] == "fap.task.complete"
    assert body["task_complete"]["envelope"]["task_id"] == inbound.envelope.task_id
    assert body["task_complete"]["payload"]["summary"] == "[SUMMARY ONLY] Matched docs: Privacy Policy Memo"
    assert body["task_complete"]["payload"]["source_refs"] == [
        {
            "participant_id": "participant_docs",
            "source_id": "doc-002",
            "source_title": "Privacy Policy Memo",
            "source_path": body["task_complete"]["payload"]["source_refs"][0]["source_path"],
        }
    ]
    assert body["task_complete"]["payload"]["source_refs"][0]["source_path"].endswith(
        "doc-002__privacy-policy-memo.json"
    )
    assert body["policy_attest"]["envelope"]["message_type"] == "fap.policy.attest"
    assert body["policy_attest"]["envelope"]["task_id"] == inbound.envelope.task_id
    assert body["policy_attest"]["envelope"]["run_id"] == inbound.envelope.run_id
    assert body["policy_attest"]["envelope"]["trace_id"] == inbound.envelope.trace_id
    assert body["policy_attest"]["envelope"]["sender_id"] == "participant_docs"
    assert body["policy_attest"]["envelope"]["recipient_id"] == inbound.envelope.sender_id
    assert body["policy_attest"]["envelope"]["domain_id"] == "participant_docs"
    assert body["policy_attest"]["payload"]["original_privacy_class"] == "internal"
    assert body["policy_attest"]["payload"]["applied_sharing_mode"] == "summary_only"
    assert body["aggregate_submit"]["envelope"]["message_type"] == "fap.aggregate.submit"
    assert body["aggregate_submit"]["envelope"]["task_id"] == inbound.envelope.task_id
    assert body["aggregate_submit"]["envelope"]["run_id"] == inbound.envelope.run_id
    assert body["aggregate_submit"]["envelope"]["trace_id"] == inbound.envelope.trace_id
    assert body["aggregate_submit"]["envelope"]["sender_id"] == "participant_docs"
    assert body["aggregate_submit"]["envelope"]["recipient_id"] == inbound.envelope.sender_id
    assert body["aggregate_submit"]["envelope"]["domain_id"] == "participant_docs"
    assert body["aggregate_submit"]["payload"]["participant_id"] == "participant_docs"
    assert body["aggregate_submit"]["payload"]["contribution_type"] == "summary"
    assert (
        body["aggregate_submit"]["payload"]["summary"]
        == body["task_complete"]["payload"]["summary"]
    )
    assert (
        body["aggregate_submit"]["payload"]["source_refs"]
        == body["task_complete"]["payload"]["source_refs"]
    )
    assert (
        body["aggregate_submit"]["payload"]["provenance_ref"]
        == body["policy_attest"]["envelope"]["message_id"]
    )


def test_execute_endpoint_public_raw_returns_raw_export() -> None:
    """Public raw governance should preserve raw export content in task-complete."""
    inbound = build_task_create_message(
        input_query="privacy",
        governance=GovernanceMetadata(
            privacy_class=PrivacyClass.PUBLIC,
            sharing_mode=SharingMode.RAW,
            policy_ref="policy.docs.v0",
        ),
    )

    response = client.post("/execute", json=message_to_dict(inbound))

    assert response.status_code == 200
    assert response.json()["task_complete"]["payload"]["summary"] == "Matched docs: Privacy Policy Memo"


def test_execute_endpoint_internal_raw_returns_redacted_export() -> None:
    """Internal raw governance should return redacted task-complete content."""
    inbound = build_task_create_message(
        input_query="privacy",
        governance=GovernanceMetadata(
            privacy_class=PrivacyClass.INTERNAL,
            sharing_mode=SharingMode.RAW,
            policy_ref="policy.docs.v0",
        ),
    )

    response = client.post("/execute", json=message_to_dict(inbound))

    assert response.status_code == 200
    assert (
        response.json()["task_complete"]["payload"]["summary"]
        == "[REDACTED EXPORT] Matched docs: Privacy Policy Memo"
    )


def test_execute_endpoint_restricted_summary_only_returns_vote_only_output() -> None:
    """Restricted summary-only governance should collapse to vote-only output."""
    inbound = build_task_create_message(
        input_query="privacy",
        governance=GovernanceMetadata(
            privacy_class=PrivacyClass.RESTRICTED,
            sharing_mode=SharingMode.SUMMARY_ONLY,
            policy_ref="policy.docs.v0",
        ),
    )

    response = client.post("/execute", json=message_to_dict(inbound))

    assert response.status_code == 200
    assert response.json()["task_complete"]["payload"]["summary"] == "[VOTE ONLY] No content exported"


def test_execute_endpoint_rejects_non_task_create_messages() -> None:
    """Only task-create messages should be supported by the execution endpoint."""
    response = client.post("/execute", json=message_to_dict(build_exception_message()))

    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "code": "unsupported_execution_message",
            "message": "participant_docs can only execute 'fap.task.create' messages",
        }
    }


def test_execute_endpoint_rejects_malformed_known_kind_payload() -> None:
    """Malformed task-create payloads should reuse the shared parse error mapping."""
    raw_message = message_to_dict(build_task_create_message(input_query="privacy"))
    payload = raw_message["payload"]
    assert isinstance(payload, dict)
    payload["title"] = "   "

    response = client.post("/execute", json=raw_message)

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "invalid_message",
            "message": "Failed to parse message kind 'fap.task.create'.",
        }
    }


def test_health_endpoint_still_works() -> None:
    """Participant docs health route should still be available."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "participant_docs"}

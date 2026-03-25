"""Tests for the coordinator->participant_docs execute-dispatch API loop."""

from __future__ import annotations

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.testclient import TestClient

from coordinator_api.main import create_app as create_coordinator_app
from fap_core import message_to_dict
from fap_core.clocks import utc_now
from fap_core.enums import (
    AggregateContributionType,
    MessageType,
    PolicyTransformType,
    PrivacyClass,
    SharingMode,
    TaskCompleteStatus,
)
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import (
    AggregateSubmitMessage,
    AggregateSubmitPayload,
    MessageEnvelope,
    PolicyAttestMessage,
    PolicyAttestPayload,
    TaskCompleteMessage,
    TaskCompletePayload,
    TaskCreateMessage,
    TaskCreatePayload,
)
from participant_docs.main import create_app as create_participant_docs_app


def build_client(participant_app: FastAPI) -> TestClient:
    """Return a fresh coordinator client wired to an in-process participant_docs app."""
    transport = httpx.ASGITransport(app=participant_app)
    return TestClient(create_coordinator_app(participant_docs_transport=transport))


def build_task_create_message() -> TaskCreateMessage:
    """Return a valid task-create message for execute-dispatch API tests."""
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
            title="Search local docs",
            description="Perform a deterministic local docs search.",
            requested_capabilities=["docs.search"],
            input_query="privacy",
        ),
    )


def create_non_200_participant_app() -> FastAPI:
    """Return a participant app stub that fails execution with a non-200 response."""
    app = FastAPI()

    @app.post("/execute")
    async def execute() -> JSONResponse:
        return JSONResponse({"detail": "nope"}, status_code=503)

    return app


def create_malformed_participant_app() -> FastAPI:
    """Return a participant app stub that responds with malformed JSON for execution."""
    app = FastAPI()

    @app.post("/execute")
    async def execute() -> PlainTextResponse:
        return PlainTextResponse("not-json", status_code=200)

    return app


def create_identity_mismatch_participant_app(
    *,
    task_complete_sender_id: str = "participant_docs",
    task_complete_domain_id: str = "participant_docs",
    aggregate_submit_sender_id: str = "participant_docs",
    aggregate_submit_domain_id: str = "participant_docs",
) -> FastAPI:
    """Return a participant app stub with mismatched execute identity fields."""
    app = FastAPI()

    @app.post("/execute")
    async def execute() -> dict[str, object]:
        task_complete = TaskCompleteMessage(
            envelope=MessageEnvelope(
                message_type=MessageType.FAP_TASK_COMPLETE,
                task_id=new_task_id(),
                run_id=new_run_id(),
                message_id=new_message_id(),
                sender_id=task_complete_sender_id,
                recipient_id="coordinator",
                domain_id=task_complete_domain_id,
                trace_id=new_trace_id(),
                timestamp=utc_now(),
            ),
            payload=TaskCompletePayload(
                participant_id="participant_docs",
                status=TaskCompleteStatus.COMPLETED,
                summary="[SUMMARY ONLY] Matched docs: Privacy Policy Memo",
            ),
        )
        policy_attest = PolicyAttestMessage(
            envelope=MessageEnvelope(
                message_type=MessageType.FAP_POLICY_ATTEST,
                task_id=new_task_id(),
                run_id=new_run_id(),
                message_id=new_message_id(),
                sender_id="participant_docs",
                recipient_id="coordinator",
                domain_id="participant_docs",
                trace_id=new_trace_id(),
                timestamp=utc_now(),
            ),
            payload=PolicyAttestPayload(
                participant_id="participant_docs",
                policy_ref="policy.docs.v0",
                original_privacy_class=PrivacyClass.INTERNAL,
                applied_sharing_mode=SharingMode.SUMMARY_ONLY,
                transform_type=PolicyTransformType.SUMMARY_ONLY,
            ),
        )
        aggregate_submit = AggregateSubmitMessage(
            envelope=MessageEnvelope(
                message_type=MessageType.FAP_AGGREGATE_SUBMIT,
                task_id=new_task_id(),
                run_id=new_run_id(),
                message_id=new_message_id(),
                sender_id=aggregate_submit_sender_id,
                recipient_id="coordinator",
                domain_id=aggregate_submit_domain_id,
                trace_id=new_trace_id(),
                timestamp=utc_now(),
            ),
            payload=AggregateSubmitPayload(
                participant_id="participant_docs",
                contribution_type=AggregateContributionType.SUMMARY,
                summary="[SUMMARY ONLY] Matched docs: Privacy Policy Memo",
                provenance_ref=policy_attest.envelope.message_id,
            ),
        )
        return {
            "task_complete": message_to_dict(task_complete),
            "policy_attest": message_to_dict(policy_attest),
            "aggregate_submit": message_to_dict(aggregate_submit),
        }

    return app


def test_dispatch_execute_returns_three_canonical_messages() -> None:
    """Dispatching a stored run to execute should return task-complete, policy-attest, and aggregate-submit."""
    client = build_client(create_participant_docs_app())
    create_message = build_task_create_message()

    create_response = client.post("/messages", json=message_to_dict(create_message))
    dispatch_response = client.post(
        f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute"
    )

    body = dispatch_response.json()
    assert create_response.status_code == 202
    assert dispatch_response.status_code == 200
    assert body["task_complete"]["envelope"]["message_type"] == "fap.task.complete"
    assert body["task_complete"]["envelope"]["task_id"] == create_message.envelope.task_id
    assert body["task_complete"]["payload"]["participant_id"] == "participant_docs"
    assert body["policy_attest"]["envelope"]["message_type"] == "fap.policy.attest"
    assert body["policy_attest"]["envelope"]["task_id"] == create_message.envelope.task_id
    assert body["policy_attest"]["envelope"]["run_id"] == create_message.envelope.run_id
    assert body["policy_attest"]["envelope"]["trace_id"] == create_message.envelope.trace_id
    assert body["policy_attest"]["payload"]["participant_id"] == "participant_docs"
    assert body["aggregate_submit"]["envelope"]["message_type"] == "fap.aggregate.submit"
    assert body["aggregate_submit"]["envelope"]["task_id"] == create_message.envelope.task_id
    assert body["aggregate_submit"]["envelope"]["run_id"] == create_message.envelope.run_id
    assert body["aggregate_submit"]["envelope"]["trace_id"] == create_message.envelope.trace_id
    assert body["aggregate_submit"]["payload"]["participant_id"] == "participant_docs"
    assert body["aggregate_submit"]["payload"]["provenance_ref"] == (
        body["policy_attest"]["envelope"]["message_id"]
    )


def test_get_run_reflects_completed_participants_after_execute_dispatch() -> None:
    """The run snapshot should include structured completions after execute dispatch."""
    client = build_client(create_participant_docs_app())
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute")
    run_response = client.get(f"/runs/{create_message.envelope.run_id}")

    assert run_response.status_code == 200
    completed_participants = run_response.json()["completed_participants"]
    assert len(completed_participants) == 1
    assert completed_participants[0]["participant_id"] == "participant_docs"
    assert completed_participants[0]["status"] == "completed"
    assert completed_participants[0]["summary"] == "[SUMMARY ONLY] Matched docs: Privacy Policy Memo"
    assert completed_participants[0]["message_id"]
    assert completed_participants[0]["source_refs"][0]["source_id"] == "doc-002"


def test_get_run_reflects_policy_attestations_after_execute_dispatch() -> None:
    """The run snapshot should include structured policy attestations after execute dispatch."""
    client = build_client(create_participant_docs_app())
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute")
    run_response = client.get(f"/runs/{create_message.envelope.run_id}")

    assert run_response.status_code == 200
    policy_attestations = run_response.json()["policy_attestations"]
    assert len(policy_attestations) == 1
    assert policy_attestations[0]["participant_id"] == "participant_docs"
    assert policy_attestations[0]["policy_ref"] == "policy.docs.v0"
    assert policy_attestations[0]["original_privacy_class"] == "internal"
    assert policy_attestations[0]["applied_sharing_mode"] == "summary_only"
    assert policy_attestations[0]["transform_type"] == "summary_only"
    assert policy_attestations[0]["message_id"]


def test_get_run_reflects_aggregate_submissions_after_execute_dispatch() -> None:
    """The run snapshot should include coordinator-generated aggregate submissions."""
    client = build_client(create_participant_docs_app())
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute")
    run_response = client.get(f"/runs/{create_message.envelope.run_id}")

    assert run_response.status_code == 200
    aggregate_submissions = run_response.json()["aggregate_submissions"]
    assert len(aggregate_submissions) == 1
    assert aggregate_submissions[0]["participant_id"] == "participant_docs"
    assert aggregate_submissions[0]["contribution_type"] == "summary"
    assert aggregate_submissions[0]["summary"] == (
        "[SUMMARY ONLY] Matched docs: Privacy Policy Memo"
    )
    assert aggregate_submissions[0]["provenance_ref"]
    assert aggregate_submissions[0]["message_id"]
    assert aggregate_submissions[0]["source_refs"][0]["source_id"] == "doc-002"


def test_dispatch_execute_for_unknown_run_returns_run_not_found() -> None:
    """Execute-dispatching an unknown run should return a stable 404 response."""
    client = build_client(create_participant_docs_app())
    unknown_run_id = new_run_id()

    response = client.post(f"/runs/{unknown_run_id}/dispatch/participant-docs/execute")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "code": "run_not_found",
            "message": f"Run not found: '{unknown_run_id}'",
        }
    }


def test_downstream_non_200_becomes_participant_execution_failed() -> None:
    """Non-200 downstream execution responses should map to a 502."""
    client = build_client(create_non_200_participant_app())
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute")

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "code": "participant_execution_failed",
            "message": "participant_docs execution failed with status 503",
        }
    }


def test_downstream_malformed_response_becomes_invalid_participant_execution_response() -> None:
    """Malformed downstream execution responses should map to a 502 invalid-response error."""
    client = build_client(create_malformed_participant_app())
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute")

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "code": "invalid_participant_execution_response",
            "message": "participant_docs returned invalid JSON response",
        }
    }


def test_identity_mismatch_sender_id_becomes_participant_identity_mismatch() -> None:
    """Mismatched execute sender ids should map to a dedicated 502 trust error."""
    client = build_client(
        create_identity_mismatch_participant_app(task_complete_sender_id="participant_kb")
    )
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute")

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "code": "participant_identity_mismatch",
            "message": (
                "participant_docs returned task_complete identity mismatch: expected "
                "sender_id/domain_id/recipient_id 'participant_docs'/'participant_docs'/'coordinator', "
                "got 'participant_kb'/'participant_docs'/'coordinator'"
            ),
        }
    }


def test_identity_mismatch_domain_id_becomes_participant_identity_mismatch() -> None:
    """Mismatched execute domain ids should map to a dedicated 502 trust error."""
    client = build_client(
        create_identity_mismatch_participant_app(aggregate_submit_domain_id="docs")
    )
    create_message = build_task_create_message()

    client.post("/messages", json=message_to_dict(create_message))
    response = client.post(f"/runs/{create_message.envelope.run_id}/dispatch/participant-docs/execute")

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "code": "participant_identity_mismatch",
            "message": (
                "participant_docs returned aggregate_submit identity mismatch: expected "
                "sender_id/domain_id/recipient_id 'participant_docs'/'participant_docs'/'coordinator', "
                "got 'participant_docs'/'docs'/'coordinator'"
            ),
        }
    }


def test_health_endpoint_still_works() -> None:
    """Coordinator health route should remain available."""
    client = build_client(create_participant_docs_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "coordinator_api"}

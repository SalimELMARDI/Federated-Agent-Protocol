"""Tests for the coordinator participant_docs execute-dispatch service."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse

from coordinator_api.service.dispatch import (
    InvalidParticipantExecutionResponseError,
    ParticipantExecutionFailedError,
    ParticipantIdentityMismatchError,
    dispatch_run_to_participant_docs_execute,
)
from coordinator_api.service.store import InMemoryRunStore
from fap_core import message_to_dict
from fap_core.clocks import utc_now
from fap_core.enums import (
    AggregateContributionType,
    PolicyTransformType,
    MessageType,
    PrivacyClass,
    RunStatus,
    SharingMode,
    TaskCompleteStatus,
)
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import (
    AggregateSubmitMessage,
    AggregateSubmitPayload,
    ExceptionMessage,
    ExceptionPayload,
    GovernanceMetadata,
    MessageEnvelope,
    PolicyAttestMessage,
    PolicyAttestPayload,
    TaskCompleteMessage,
    TaskCompletePayload,
    TaskCreateMessage,
    TaskCreatePayload,
)
from participant_docs.main import create_app as create_participant_docs_app


def build_create_message(*, governance: GovernanceMetadata | None = None) -> TaskCreateMessage:
    """Return a valid task-create message for execute-dispatch tests."""
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
            governance=governance,
        ),
        payload=TaskCreatePayload(
            title="Search local docs",
            description="Perform a deterministic local docs search.",
            requested_capabilities=["docs.search"],
            input_query="privacy",
        ),
    )


def create_wrong_type_execution_app() -> FastAPI:
    """Return an app that serves a wrong aggregate-submit message type."""
    app = FastAPI()

    @app.post("/execute")
    async def execute() -> dict[str, object]:
        task_complete = TaskCompleteMessage(
            envelope=MessageEnvelope(
                message_type=MessageType.FAP_TASK_COMPLETE,
                task_id=new_task_id(),
                run_id=new_run_id(),
                message_id=new_message_id(),
                sender_id="participant_docs",
                recipient_id="coordinator",
                domain_id="participant_docs",
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
        aggregate_submit = ExceptionMessage(
            envelope=MessageEnvelope(
                message_type=MessageType.FAP_EXCEPTION,
                task_id=new_task_id(),
                run_id=new_run_id(),
                message_id=new_message_id(),
                sender_id="participant_docs",
                recipient_id="coordinator",
                domain_id="participant_docs",
                trace_id=new_trace_id(),
                timestamp=utc_now(),
            ),
            payload=ExceptionPayload(
                code="participant.unavailable",
                message="The participant could not access its local source.",
            ),
        )
        return {
            "task_complete": message_to_dict(task_complete),
            "policy_attest": message_to_dict(policy_attest),
            "aggregate_submit": message_to_dict(aggregate_submit),
        }

    return app


def create_identity_mismatch_execution_app(
    *,
    task_complete_sender_id: str = "participant_docs",
    task_complete_domain_id: str = "participant_docs",
    policy_attest_sender_id: str = "participant_docs",
    policy_attest_domain_id: str = "participant_docs",
    aggregate_submit_sender_id: str = "participant_docs",
    aggregate_submit_domain_id: str = "participant_docs",
) -> FastAPI:
    """Return an app that serves a valid execution bundle with mismatched identity fields."""
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
                sender_id=policy_attest_sender_id,
                recipient_id="coordinator",
                domain_id=policy_attest_domain_id,
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


@pytest.mark.anyio
async def test_execute_dispatch_returns_parsed_task_complete_policy_attest_and_aggregate_submit() -> None:
    """Supported execute dispatch should return all three typed execution messages."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)

    result = await dispatch_run_to_participant_docs_execute(
        create_message.envelope.run_id,
        store=store,
        execute_url="http://participant-docs/execute",
        transport=httpx.ASGITransport(app=create_participant_docs_app()),
    )

    assert result.task_complete_message.envelope.message_type == MessageType.FAP_TASK_COMPLETE
    assert result.policy_attest_message.envelope.message_type == MessageType.FAP_POLICY_ATTEST
    assert result.aggregate_submit_message.envelope.message_type == MessageType.FAP_AGGREGATE_SUBMIT
    assert result.policy_attest_message.envelope.task_id == create_message.envelope.task_id
    assert result.policy_attest_message.envelope.run_id == create_message.envelope.run_id
    assert result.policy_attest_message.envelope.trace_id == create_message.envelope.trace_id
    assert result.aggregate_submit_message.envelope.task_id == create_message.envelope.task_id
    assert result.aggregate_submit_message.envelope.run_id == create_message.envelope.run_id
    assert result.aggregate_submit_message.envelope.trace_id == create_message.envelope.trace_id
    assert result.task_complete_message.payload.source_refs[0].source_id == "doc-002"
    assert result.aggregate_submit_message.payload.source_refs == result.task_complete_message.payload.source_refs


@pytest.mark.anyio
async def test_execute_dispatch_records_all_three_messages_into_the_store() -> None:
    """Execute dispatch should persist completion, policy attestation, and aggregate submit."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)

    await dispatch_run_to_participant_docs_execute(
        create_message.envelope.run_id,
        store=store,
        execute_url="http://participant-docs/execute",
        transport=httpx.ASGITransport(app=create_participant_docs_app()),
    )

    snapshot = store.get_run(create_message.envelope.run_id)
    assert snapshot is not None
    assert snapshot.completed_participants[0].participant_id == "participant_docs"
    assert snapshot.completed_participants[0].source_refs[0].source_id == "doc-002"
    assert snapshot.policy_attestations[0].participant_id == "participant_docs"
    assert snapshot.aggregate_submissions[0].participant_id == "participant_docs"
    assert snapshot.aggregate_submissions[0].source_refs[0].source_id == "doc-002"
    assert snapshot.status == RunStatus.COMPLETED_RECORDED
    assert snapshot.last_message_type == "fap.aggregate.submit"
    assert snapshot.message_count == 4


@pytest.mark.anyio
async def test_execute_dispatch_non_200_response_raises_expected_error() -> None:
    """Non-200 downstream execute responses should become coordinator dispatch errors."""
    app = FastAPI()

    @app.post("/execute")
    async def execute() -> JSONResponse:
        return JSONResponse({"detail": "nope"}, status_code=503)

    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)

    with pytest.raises(
        ParticipantExecutionFailedError,
        match="participant_docs execution failed with status 503",
    ):
        await dispatch_run_to_participant_docs_execute(
            create_message.envelope.run_id,
            store=store,
            execute_url="http://participant-docs/execute",
            transport=httpx.ASGITransport(app=app),
        )


@pytest.mark.anyio
async def test_execute_dispatch_malformed_response_raises_expected_error() -> None:
    """Malformed downstream execute payloads should become invalid-response errors."""
    app = FastAPI()

    @app.post("/execute")
    async def execute() -> PlainTextResponse:
        return PlainTextResponse("not-json", status_code=200)

    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)

    with pytest.raises(
        InvalidParticipantExecutionResponseError,
        match="participant_docs returned invalid JSON response",
    ):
        await dispatch_run_to_participant_docs_execute(
            create_message.envelope.run_id,
            store=store,
            execute_url="http://participant-docs/execute",
            transport=httpx.ASGITransport(app=app),
        )


@pytest.mark.anyio
async def test_execute_dispatch_missing_expected_fields_raises_expected_error() -> None:
    """Missing aggregate_submit should be rejected."""
    app = FastAPI()

    @app.post("/execute")
    async def execute() -> dict[str, object]:
        task_complete = TaskCompleteMessage(
            envelope=MessageEnvelope(
                message_type=MessageType.FAP_TASK_COMPLETE,
                task_id=new_task_id(),
                run_id=new_run_id(),
                message_id=new_message_id(),
                sender_id="participant_docs",
                recipient_id="coordinator",
                domain_id="participant_docs",
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
        return {
            "task_complete": message_to_dict(task_complete),
            "policy_attest": message_to_dict(policy_attest),
        }

    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)

    with pytest.raises(
        InvalidParticipantExecutionResponseError,
        match="participant_docs execution response is missing 'aggregate_submit'",
    ):
        await dispatch_run_to_participant_docs_execute(
            create_message.envelope.run_id,
            store=store,
            execute_url="http://participant-docs/execute",
            transport=httpx.ASGITransport(app=app),
        )


@pytest.mark.anyio
async def test_execute_dispatch_wrong_aggregate_submit_message_type_raises_expected_error() -> None:
    """Valid but unexpected aggregate-submit message kinds should be rejected."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)

    with pytest.raises(
        InvalidParticipantExecutionResponseError,
        match="participant_docs returned unexpected execution message types",
    ):
        await dispatch_run_to_participant_docs_execute(
            create_message.envelope.run_id,
            store=store,
            execute_url="http://participant-docs/execute",
            transport=httpx.ASGITransport(app=create_wrong_type_execution_app()),
        )


@pytest.mark.anyio
async def test_execute_dispatch_sender_id_mismatch_raises_identity_mismatch_error() -> None:
    """Execute dispatch should reject governed outputs from the wrong sender id."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)

    with pytest.raises(
        ParticipantIdentityMismatchError,
        match="expected sender_id/domain_id/recipient_id 'participant_docs'/'participant_docs'/'coordinator'",
    ):
        await dispatch_run_to_participant_docs_execute(
            create_message.envelope.run_id,
            store=store,
            execute_url="http://participant-docs/execute",
            transport=httpx.ASGITransport(
                app=create_identity_mismatch_execution_app(task_complete_sender_id="participant_kb")
            ),
        )


@pytest.mark.anyio
async def test_execute_dispatch_domain_id_mismatch_raises_identity_mismatch_error() -> None:
    """Execute dispatch should reject governed outputs from the wrong domain id."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)

    with pytest.raises(
        ParticipantIdentityMismatchError,
        match="expected sender_id/domain_id/recipient_id 'participant_docs'/'participant_docs'/'coordinator'",
    ):
        await dispatch_run_to_participant_docs_execute(
            create_message.envelope.run_id,
            store=store,
            execute_url="http://participant-docs/execute",
            transport=httpx.ASGITransport(
                app=create_identity_mismatch_execution_app(aggregate_submit_domain_id="docs")
            ),
        )

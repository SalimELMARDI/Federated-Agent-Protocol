"""Tests for the coordinator participant_docs dispatch service."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse

from coordinator_api.service.dispatch import (
    InvalidParticipantResponseError,
    ParticipantEvaluationFailedError,
    ParticipantIdentityMismatchError,
    dispatch_run_to_participant_docs,
)
from coordinator_api.service.store import InMemoryRunStore
from fap_core import message_to_dict
from fap_core.clocks import utc_now
from fap_core.enums import MessageType
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import (
    ExceptionMessage,
    ExceptionPayload,
    MessageEnvelope,
    TaskAcceptMessage,
    TaskAcceptPayload,
    TaskCreateMessage,
    TaskCreatePayload,
    TaskRejectMessage,
)
from participant_docs.main import create_app as create_participant_docs_app


def build_create_message(requested_capabilities: list[str]) -> TaskCreateMessage:
    """Return a valid task-create message for dispatch tests."""
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
            title="Summarize notes",
            description="Create a redacted summary for coordinator review.",
            requested_capabilities=requested_capabilities,
            input_query="Summarize the incident notes.",
        ),
    )


def create_invalid_decision_app() -> FastAPI:
    """Return an app that serves a valid but unsupported FAP decision message."""
    app = FastAPI()

    @app.post("/evaluate")
    async def evaluate() -> dict[str, object]:
        message = ExceptionMessage(
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
        return message_to_dict(message)

    return app


def create_identity_mismatch_decision_app(
    *,
    sender_id: str = "participant_docs",
    domain_id: str = "participant_docs",
    recipient_id: str = "coordinator",
) -> FastAPI:
    """Return an app that serves a valid decision with mismatched identity fields."""
    app = FastAPI()

    @app.post("/evaluate")
    async def evaluate() -> dict[str, object]:
        message = TaskAcceptMessage(
            envelope=MessageEnvelope(
                message_type=MessageType.FAP_TASK_ACCEPT,
                task_id=new_task_id(),
                run_id=new_run_id(),
                message_id=new_message_id(),
                sender_id=sender_id,
                recipient_id=recipient_id,
                domain_id=domain_id,
                trace_id=new_trace_id(),
                timestamp=utc_now(),
            ),
            payload=TaskAcceptPayload(
                participant_id="participant_docs",
                accepted_capabilities=["docs.lookup"],
            ),
        )
        return message_to_dict(message)

    return app


@pytest.mark.anyio
async def test_dispatch_returns_task_accept_for_supported_input() -> None:
    """Supported task-create messages should yield a parsed task-accept decision."""
    store = InMemoryRunStore()
    create_message = build_create_message(["docs.lookup", "docs.summarize"])
    store.record_task_create(create_message)
    transport = httpx.ASGITransport(app=create_participant_docs_app())

    decision = await dispatch_run_to_participant_docs(
        create_message.envelope.run_id,
        store=store,
        evaluate_url="http://participant-docs/evaluate",
        transport=transport,
    )

    assert isinstance(decision, TaskAcceptMessage)
    assert decision.payload.accepted_capabilities == ["docs.lookup", "docs.summarize"]


@pytest.mark.anyio
async def test_dispatch_returns_task_reject_for_unsupported_input() -> None:
    """Unsupported capabilities should yield a parsed task-reject decision."""
    store = InMemoryRunStore()
    create_message = build_create_message(["docs.lookup", "docs.translate"])
    store.record_task_create(create_message)
    transport = httpx.ASGITransport(app=create_participant_docs_app())

    decision = await dispatch_run_to_participant_docs(
        create_message.envelope.run_id,
        store=store,
        evaluate_url="http://participant-docs/evaluate",
        transport=transport,
    )

    assert isinstance(decision, TaskRejectMessage)
    assert "docs.translate" in decision.payload.reason


@pytest.mark.anyio
async def test_dispatch_records_the_returned_decision_into_the_store() -> None:
    """Dispatch should persist the returned participant decision into run state."""
    store = InMemoryRunStore()
    create_message = build_create_message(["docs.lookup"])
    store.record_task_create(create_message)
    transport = httpx.ASGITransport(app=create_participant_docs_app())

    await dispatch_run_to_participant_docs(
        create_message.envelope.run_id,
        store=store,
        evaluate_url="http://participant-docs/evaluate",
        transport=transport,
    )

    snapshot = store.get_run(create_message.envelope.run_id)
    assert snapshot is not None
    assert snapshot.accepted_participants == ["participant_docs"]
    assert snapshot.last_message_type == "fap.task.accept"
    assert snapshot.message_count == 2


@pytest.mark.anyio
async def test_downstream_non_200_response_raises_expected_error() -> None:
    """Non-200 downstream responses should become coordinator dispatch errors."""
    app = FastAPI()

    @app.post("/evaluate")
    async def evaluate() -> JSONResponse:
        return JSONResponse({"detail": "nope"}, status_code=503)

    store = InMemoryRunStore()
    create_message = build_create_message(["docs.lookup"])
    store.record_task_create(create_message)

    with pytest.raises(
        ParticipantEvaluationFailedError,
        match="participant_docs evaluation failed with status 503",
    ):
        await dispatch_run_to_participant_docs(
            create_message.envelope.run_id,
            store=store,
            evaluate_url="http://participant-docs/evaluate",
            transport=httpx.ASGITransport(app=app),
        )


@pytest.mark.anyio
async def test_malformed_downstream_response_raises_expected_error() -> None:
    """Malformed downstream payloads should become invalid-response errors."""
    app = FastAPI()

    @app.post("/evaluate")
    async def evaluate() -> PlainTextResponse:
        return PlainTextResponse("not-json", status_code=200)

    store = InMemoryRunStore()
    create_message = build_create_message(["docs.lookup"])
    store.record_task_create(create_message)

    with pytest.raises(
        InvalidParticipantResponseError,
        match="participant_docs returned invalid JSON response",
    ):
        await dispatch_run_to_participant_docs(
            create_message.envelope.run_id,
            store=store,
            evaluate_url="http://participant-docs/evaluate",
            transport=httpx.ASGITransport(app=app),
        )


@pytest.mark.anyio
async def test_unsupported_downstream_fap_message_type_raises_expected_error() -> None:
    """Valid but unsupported downstream FAP messages should be rejected."""
    store = InMemoryRunStore()
    create_message = build_create_message(["docs.lookup"])
    store.record_task_create(create_message)

    with pytest.raises(
        InvalidParticipantResponseError,
        match="participant_docs returned unsupported decision message type: 'fap.exception'",
    ):
        await dispatch_run_to_participant_docs(
            create_message.envelope.run_id,
            store=store,
            evaluate_url="http://participant-docs/evaluate",
            transport=httpx.ASGITransport(app=create_invalid_decision_app()),
        )


@pytest.mark.anyio
async def test_sender_id_mismatch_raises_identity_mismatch_error() -> None:
    """Evaluate dispatch should reject decisions from the wrong participant sender id."""
    store = InMemoryRunStore()
    create_message = build_create_message(["docs.lookup"])
    store.record_task_create(create_message)

    with pytest.raises(
        ParticipantIdentityMismatchError,
        match="expected sender_id/domain_id/recipient_id 'participant_docs'/'participant_docs'/'coordinator'",
    ):
        await dispatch_run_to_participant_docs(
            create_message.envelope.run_id,
            store=store,
            evaluate_url="http://participant-docs/evaluate",
            transport=httpx.ASGITransport(
                app=create_identity_mismatch_decision_app(sender_id="participant_kb")
            ),
        )


@pytest.mark.anyio
async def test_domain_id_mismatch_raises_identity_mismatch_error() -> None:
    """Evaluate dispatch should reject decisions from the wrong participant domain id."""
    store = InMemoryRunStore()
    create_message = build_create_message(["docs.lookup"])
    store.record_task_create(create_message)

    with pytest.raises(
        ParticipantIdentityMismatchError,
        match="expected sender_id/domain_id/recipient_id 'participant_docs'/'participant_docs'/'coordinator'",
    ):
        await dispatch_run_to_participant_docs(
            create_message.envelope.run_id,
            store=store,
            evaluate_url="http://participant-docs/evaluate",
            transport=httpx.ASGITransport(
                app=create_identity_mismatch_decision_app(domain_id="docs")
            ),
        )

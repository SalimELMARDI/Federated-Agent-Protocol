"""Dispatch routes for the coordinator service."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from coordinator_api.service.dispatch import (
    InvalidParticipantExecutionResponseError,
    InvalidParticipantResponseError,
    ParticipantIdentityMismatchError,
    ParticipantExecutionDispatchResult,
    ParticipantExecutionFailedError,
    ParticipantEvaluationFailedError,
    RunNotFoundError,
    TrustedParticipantConfig,
    dispatch_run_to_participant_kb,
    dispatch_run_to_participant_kb_execute,
    dispatch_run_to_participant_logs,
    dispatch_run_to_participant_logs_execute,
    dispatch_run_to_participant_docs,
    dispatch_run_to_participant_docs_execute,
)
from coordinator_api.service.persistence import PersistenceError, PersistenceService
from coordinator_api.service.store import CoordinatorStore, InMemoryRunStore
from fap_core import message_to_dict
from fap_core.identity import ParticipantId
from fap_core.messages import SupportedMessage

router = APIRouter()


class ParticipantExecuteDispatchResponse(BaseModel):
    """Canonical coordinator response for participant_docs execution dispatch."""

    model_config = ConfigDict(extra="forbid")

    task_complete: dict[str, object]
    policy_attest: dict[str, object]
    aggregate_submit: dict[str, object]


@router.post("/runs/{run_id}/dispatch/participant-docs")
async def dispatch_participant_docs(run_id: str, request: Request) -> dict[str, object]:
    """Dispatch a stored run to participant_docs evaluation and return the decision message."""
    store = _get_store(request)
    participant = _get_trusted_participant(request, ParticipantId.PARTICIPANT_DOCS)

    try:
        decision = await dispatch_run_to_participant_docs(
            run_id,
            store=store,
            evaluate_url=participant.evaluate_url,
            transport=participant.transport,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": str(exc)},
        ) from exc
    except ParticipantIdentityMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_identity_mismatch", "message": str(exc)},
        ) from exc
    except ParticipantEvaluationFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_evaluation_failed", "message": str(exc)},
        ) from exc
    except InvalidParticipantResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_participant_response", "message": str(exc)},
        ) from exc
    except PersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failed", "message": str(exc)},
        ) from exc

    _persist_dispatch_messages(request, run_id=run_id, messages=[decision])

    return message_to_dict(decision)


@router.post(
    "/runs/{run_id}/dispatch/participant-docs/execute",
    response_model=ParticipantExecuteDispatchResponse,
)
async def dispatch_participant_docs_execute(
    run_id: str, request: Request
) -> ParticipantExecuteDispatchResponse:
    """Dispatch a stored run to participant_docs execution and return governed outputs."""
    store = _get_store(request)
    participant = _get_trusted_participant(request, ParticipantId.PARTICIPANT_DOCS)

    try:
        result = await dispatch_run_to_participant_docs_execute(
            run_id,
            store=store,
            execute_url=participant.execute_url,
            transport=participant.transport,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": str(exc)},
        ) from exc
    except ParticipantIdentityMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_identity_mismatch", "message": str(exc)},
        ) from exc
    except ParticipantExecutionFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_execution_failed", "message": str(exc)},
        ) from exc
    except InvalidParticipantExecutionResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_participant_execution_response", "message": str(exc)},
        ) from exc
    except PersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failed", "message": str(exc)},
        ) from exc

    _persist_dispatch_messages(
        request,
        run_id=run_id,
        messages=[
            result.task_complete_message,
            result.policy_attest_message,
            result.aggregate_submit_message,
        ],
    )

    return _build_execute_response(result)


@router.post("/runs/{run_id}/dispatch/participant-kb")
async def dispatch_participant_kb(run_id: str, request: Request) -> dict[str, object]:
    """Dispatch a stored run to participant_kb evaluation and return the decision message."""
    store = _get_store(request)
    participant = _get_trusted_participant(request, ParticipantId.PARTICIPANT_KB)

    try:
        decision = await dispatch_run_to_participant_kb(
            run_id,
            store=store,
            evaluate_url=participant.evaluate_url,
            transport=participant.transport,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": str(exc)},
        ) from exc
    except ParticipantIdentityMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_identity_mismatch", "message": str(exc)},
        ) from exc
    except ParticipantEvaluationFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_evaluation_failed", "message": str(exc)},
        ) from exc
    except InvalidParticipantResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_participant_response", "message": str(exc)},
        ) from exc
    except PersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failed", "message": str(exc)},
        ) from exc

    _persist_dispatch_messages(request, run_id=run_id, messages=[decision])
    return message_to_dict(decision)


@router.post("/runs/{run_id}/dispatch/participant-logs")
async def dispatch_participant_logs(run_id: str, request: Request) -> dict[str, object]:
    """Dispatch a stored run to participant_logs evaluation and return the decision message."""
    store = _get_store(request)
    participant = _get_trusted_participant(request, ParticipantId.PARTICIPANT_LOGS)

    try:
        decision = await dispatch_run_to_participant_logs(
            run_id,
            store=store,
            evaluate_url=participant.evaluate_url,
            transport=participant.transport,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": str(exc)},
        ) from exc
    except ParticipantIdentityMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_identity_mismatch", "message": str(exc)},
        ) from exc
    except ParticipantEvaluationFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_evaluation_failed", "message": str(exc)},
        ) from exc
    except InvalidParticipantResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_participant_response", "message": str(exc)},
        ) from exc
    except PersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failed", "message": str(exc)},
        ) from exc

    _persist_dispatch_messages(request, run_id=run_id, messages=[decision])
    return message_to_dict(decision)


@router.post(
    "/runs/{run_id}/dispatch/participant-kb/execute",
    response_model=ParticipantExecuteDispatchResponse,
)
async def dispatch_participant_kb_execute(
    run_id: str, request: Request
) -> ParticipantExecuteDispatchResponse:
    """Dispatch a stored run to participant_kb execution and return governed outputs."""
    store = _get_store(request)
    participant = _get_trusted_participant(request, ParticipantId.PARTICIPANT_KB)

    try:
        result = await dispatch_run_to_participant_kb_execute(
            run_id,
            store=store,
            execute_url=participant.execute_url,
            transport=participant.transport,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": str(exc)},
        ) from exc
    except ParticipantIdentityMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_identity_mismatch", "message": str(exc)},
        ) from exc
    except ParticipantExecutionFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_execution_failed", "message": str(exc)},
        ) from exc
    except InvalidParticipantExecutionResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_participant_execution_response", "message": str(exc)},
        ) from exc
    except PersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failed", "message": str(exc)},
        ) from exc

    _persist_dispatch_messages(
        request,
        run_id=run_id,
        messages=[
            result.task_complete_message,
            result.policy_attest_message,
            result.aggregate_submit_message,
        ],
    )
    return _build_execute_response(result)


@router.post(
    "/runs/{run_id}/dispatch/participant-logs/execute",
    response_model=ParticipantExecuteDispatchResponse,
)
async def dispatch_participant_logs_execute(
    run_id: str, request: Request
) -> ParticipantExecuteDispatchResponse:
    """Dispatch a stored run to participant_logs execution and return governed outputs."""
    store = _get_store(request)
    participant = _get_trusted_participant(request, ParticipantId.PARTICIPANT_LOGS)

    try:
        result = await dispatch_run_to_participant_logs_execute(
            run_id,
            store=store,
            execute_url=participant.execute_url,
            transport=participant.transport,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": str(exc)},
        ) from exc
    except ParticipantIdentityMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_identity_mismatch", "message": str(exc)},
        ) from exc
    except ParticipantExecutionFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_execution_failed", "message": str(exc)},
        ) from exc
    except InvalidParticipantExecutionResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_participant_execution_response", "message": str(exc)},
        ) from exc
    except PersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failed", "message": str(exc)},
        ) from exc

    _persist_dispatch_messages(
        request,
        run_id=run_id,
        messages=[
            result.task_complete_message,
            result.policy_attest_message,
            result.aggregate_submit_message,
        ],
    )
    return _build_execute_response(result)


def _build_execute_response(
    result: ParticipantExecutionDispatchResult,
) -> ParticipantExecuteDispatchResponse:
    """Convert execute-dispatch output into canonical JSON-safe response data."""
    return ParticipantExecuteDispatchResponse(
        task_complete=message_to_dict(result.task_complete_message),
        policy_attest=message_to_dict(result.policy_attest_message),
        aggregate_submit=message_to_dict(result.aggregate_submit_message),
    )


def _persist_dispatch_messages(
    request: Request, *, run_id: str, messages: Sequence[SupportedMessage]
) -> None:
    """Persist dispatch-returned messages plus the updated run snapshot for legacy stores."""
    store = _get_store(request)
    if not isinstance(store, InMemoryRunStore):
        return

    snapshot = store.get_run(run_id)
    if snapshot is None:
        raise RuntimeError("Coordinator run snapshot was not found after dispatch.")

    try:
        _get_persistence_service(request).persist_messages_and_snapshot(messages, snapshot=snapshot)
    except PersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failed", "message": str(exc)},
        ) from exc


def _get_store(request: Request) -> CoordinatorStore:
    """Return the configured coordinator runtime store."""
    store = getattr(request.app.state, "run_store", None)
    if store is None:
        raise RuntimeError("Coordinator run store is not configured.")
    return cast(CoordinatorStore, store)


def _get_persistence_service(request: Request) -> PersistenceService:
    """Return the configured coordinator persistence service."""
    persistence_service = getattr(request.app.state, "persistence_service", None)
    if persistence_service is None:
        raise RuntimeError("Coordinator persistence service is not configured.")
    return cast(PersistenceService, persistence_service)


def _get_trusted_participant(
    request: Request,
    participant_id: ParticipantId,
) -> TrustedParticipantConfig:
    """Return the trusted participant configuration for a known participant."""
    trusted_participants = getattr(request.app.state, "trusted_participants", None)
    if trusted_participants is None:
        raise RuntimeError("Coordinator trusted participant registry is not configured.")

    try:
        return cast(dict[ParticipantId, TrustedParticipantConfig], trusted_participants)[participant_id]
    except KeyError as exc:
        raise RuntimeError(f"Trusted participant not configured: {participant_id.value!r}") from exc

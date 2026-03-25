"""Protocol ingress routes for the coordinator service."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Body, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from coordinator_api.service.persistence import PersistenceError, PersistenceService
from fap_core import build_accepted_response, parse_inbound_message, to_protocol_http_exception
from coordinator_api.service.store import CoordinatorStore, InMemoryRunStore, RunAlreadyExistsError, UnknownRunError

router = APIRouter()


class MessageAcceptedResponse(BaseModel):
    """Minimal acceptance response for parsed FAP messages."""

    model_config = ConfigDict(extra="forbid")

    status: str
    message_type: str
    message_id: str
    task_id: str
    run_id: str


@router.post("/messages", response_model=MessageAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_message(
    request: Request, message: dict[str, object] = Body(...)
) -> MessageAcceptedResponse:
    """Accept and parse a raw FAP message without executing business logic."""
    try:
        parsed = parse_inbound_message(message)
    except Exception as exc:
        raise to_protocol_http_exception(exc) from exc

    store = _get_store(request)
    try:
        snapshot = store.record_message(parsed)
    except RunAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "run_already_exists", "message": str(exc)},
        ) from exc
    except UnknownRunError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "unknown_run", "message": str(exc)},
        ) from exc
    except PersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failed", "message": str(exc)},
        ) from exc

    if isinstance(store, InMemoryRunStore):
        try:
            _get_persistence_service(request).persist_messages_and_snapshot(
                [parsed], snapshot=snapshot
            )
        except PersistenceError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "persistence_failed", "message": str(exc)},
            ) from exc

    return MessageAcceptedResponse(**build_accepted_response(parsed))


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

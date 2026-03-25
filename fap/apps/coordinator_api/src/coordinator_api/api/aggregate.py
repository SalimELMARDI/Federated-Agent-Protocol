"""Aggregation routes for the coordinator service."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from coordinator_api.service.aggregation import (
    AggregationRunNotFoundError,
    NoCompletedParticipantsError,
    aggregate_run_summary_merge,
)
from coordinator_api.service.persistence import PersistenceError, PersistenceService
from coordinator_api.service.store import CoordinatorStore, InMemoryRunStore
from fap_core import message_to_dict

router = APIRouter()


@router.post("/runs/{run_id}/aggregate/summary-merge")
async def aggregate_summary_merge(run_id: str, request: Request) -> dict[str, object]:
    """Aggregate recorded participant completions into a canonical aggregate-result message."""
    store = _get_store(request)

    try:
        aggregate_result = aggregate_run_summary_merge(run_id, store=store)
        snapshot = store.record_aggregate_result(aggregate_result)
    except AggregationRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": str(exc)},
        ) from exc
    except NoCompletedParticipantsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "no_completed_participants", "message": str(exc)},
        ) from exc
    except PersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failed", "message": str(exc)},
        ) from exc

    if isinstance(store, InMemoryRunStore):
        try:
            _get_persistence_service(request).persist_messages_and_snapshot(
                [aggregate_result], snapshot=snapshot
            )
        except PersistenceError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "persistence_failed", "message": str(exc)},
            ) from exc

    return message_to_dict(aggregate_result)


def _get_persistence_service(request: Request) -> PersistenceService:
    """Return the configured coordinator persistence service."""
    persistence_service = getattr(request.app.state, "persistence_service", None)
    if persistence_service is None:
        raise RuntimeError("Coordinator persistence service is not configured.")
    return persistence_service


def _get_store(request: Request) -> CoordinatorStore:
    """Return the configured coordinator runtime store."""
    store = getattr(request.app.state, "run_store", None)
    if store is None:
        raise RuntimeError("Coordinator run store is not configured.")
    return store

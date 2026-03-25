"""Run state routes for the coordinator service."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, Request, status

from coordinator_api.service.persistence import PersistenceError, PersistenceService
from coordinator_api.service.store import CoordinatorStore

router = APIRouter()


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> dict[str, object]:
    """Return the current durable run snapshot for a known run."""
    try:
        snapshot = _get_store(request).get_run(run_id)
    except PersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failed", "message": str(exc)},
        ) from exc

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": f"Run not found: {run_id!r}"},
        )

    return snapshot.model_dump(mode="json")


@router.get("/runs/{run_id}/events")
async def list_run_events(run_id: str, request: Request) -> list[dict[str, object]]:
    """Return durable protocol event summaries for a known persisted run."""
    try:
        events = _get_persistence_service(request).list_events_for_run(run_id)
    except PersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failed", "message": str(exc)},
        ) from exc

    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "run_events_not_found",
                "message": f"No persisted events found for run: {run_id!r}",
            },
        )

    return [event.model_dump(mode="json") for event in events]


def _get_persistence_service(request: Request) -> PersistenceService:
    """Return the configured coordinator persistence service."""
    persistence_service = getattr(request.app.state, "persistence_service", None)
    if persistence_service is None:
        raise RuntimeError("Coordinator persistence service is not configured.")
    return cast(PersistenceService, persistence_service)


def _get_store(request: Request) -> CoordinatorStore:
    """Return the configured coordinator runtime store."""
    store = getattr(request.app.state, "run_store", None)
    if store is None:
        raise RuntimeError("Coordinator run store is not configured.")
    return cast(CoordinatorStore, store)

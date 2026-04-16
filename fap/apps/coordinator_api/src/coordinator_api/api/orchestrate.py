"""One-shot orchestration routes for the coordinator service."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from coordinator_api.service.dispatch import (
    ParticipantIdentityMismatchError,
    RunNotFoundError,
    TrustedParticipantConfig,
)
from coordinator_api.service.orchestration import (
    NoExecutableParticipantsError,
    OrchestrationResult,
    ParticipantOrchestrationFailedError,
    orchestrate_run_summary_merge,
)
from coordinator_api.service.persistence import PersistenceError, PersistenceService
from coordinator_api.service.store import CoordinatorStore
from fap_core.identity import ParticipantId

router = APIRouter()


@router.post(
    "/runs/{run_id}/orchestrate/summary-merge",
    response_model=OrchestrationResult,
)
async def orchestrate_summary_merge(run_id: str, request: Request) -> OrchestrationResult:
    """Run a full federated summary-merge orchestration flow for an existing run."""
    trusted_participants = _get_trusted_participants(request)
    try:
        return await orchestrate_run_summary_merge(
            run_id,
            store=_get_store(request),
            persistence_service=_get_persistence_service(request),
            participant_docs_evaluate_url=trusted_participants[ParticipantId.PARTICIPANT_DOCS].evaluate_url,
            participant_docs_execute_url=trusted_participants[ParticipantId.PARTICIPANT_DOCS].execute_url,
            participant_docs_transport=trusted_participants[ParticipantId.PARTICIPANT_DOCS].transport,
            participant_kb_evaluate_url=trusted_participants[ParticipantId.PARTICIPANT_KB].evaluate_url,
            participant_kb_execute_url=trusted_participants[ParticipantId.PARTICIPANT_KB].execute_url,
            participant_kb_transport=trusted_participants[ParticipantId.PARTICIPANT_KB].transport,
            participant_logs_evaluate_url=trusted_participants[ParticipantId.PARTICIPANT_LOGS].evaluate_url,
            participant_logs_execute_url=trusted_participants[ParticipantId.PARTICIPANT_LOGS].execute_url,
            participant_logs_transport=trusted_participants[ParticipantId.PARTICIPANT_LOGS].transport,
            participant_llm_evaluate_url=trusted_participants[ParticipantId.PARTICIPANT_LLM].evaluate_url
            if ParticipantId.PARTICIPANT_LLM in trusted_participants
            else None,
            participant_llm_execute_url=trusted_participants[ParticipantId.PARTICIPANT_LLM].execute_url
            if ParticipantId.PARTICIPANT_LLM in trusted_participants
            else None,
            participant_llm_transport=trusted_participants[ParticipantId.PARTICIPANT_LLM].transport
            if ParticipantId.PARTICIPANT_LLM in trusted_participants
            else None,
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
    except NoExecutableParticipantsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "no_executable_participants", "message": str(exc)},
        ) from exc
    except ParticipantOrchestrationFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_orchestration_failed", "message": str(exc)},
        ) from exc
    except PersistenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "persistence_failed", "message": str(exc)},
        ) from exc


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


def _get_trusted_participants(request: Request) -> dict[ParticipantId, TrustedParticipantConfig]:
    """Return the configured trusted participant registry."""
    trusted_participants = getattr(request.app.state, "trusted_participants", None)
    if trusted_participants is None:
        raise RuntimeError("Coordinator trusted participant registry is not configured.")
    return trusted_participants

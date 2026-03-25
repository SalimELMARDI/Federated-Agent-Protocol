"""Thin user-facing ask route built on top of the coordinator runtime."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from coordinator_api.service.agent import AgentAskRequest, AgentRunResult, run_agent_request_summary_merge
from coordinator_api.service.dispatch import (
    ParticipantIdentityMismatchError,
    RunNotFoundError,
    TrustedParticipantConfig,
)
from coordinator_api.service.orchestration import (
    NoExecutableParticipantsError,
    ParticipantOrchestrationFailedError,
)
from coordinator_api.service.persistence import PersistenceError, PersistenceService
from coordinator_api.service.store import CoordinatorStore, RunAlreadyExistsError
from fap_core import message_to_dict
from fap_core.identity import ParticipantId

router = APIRouter()


class AskResponse(BaseModel):
    """User-facing response returned by the thin FAP ask wrapper."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    task_id: str
    created_message_id: str
    final_answer: str
    source_refs: list[dict[str, object]]
    aggregate_result: dict[str, object]
    evaluations: list[dict[str, object]]
    executions: list[dict[str, object]]
    run_path: str
    events_path: str


@router.post("/ask", response_model=AskResponse)
async def ask(request: Request, payload: AgentAskRequest) -> AskResponse:
    """Run a plain-language request through the real coordinator runtime."""
    trusted_participants = _get_trusted_participants(request)
    try:
        result = await run_agent_request_summary_merge(
            payload,
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
        )
    except RunAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "run_already_exists", "message": str(exc)},
        ) from exc
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": str(exc)},
        ) from exc
    except NoExecutableParticipantsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "no_executable_participants", "message": str(exc)},
        ) from exc
    except ParticipantIdentityMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_identity_mismatch", "message": str(exc)},
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

    return _build_response(result)


def _build_response(result: AgentRunResult) -> AskResponse:
    """Convert the agent-run result into a compact user-facing payload."""
    aggregate_result = result.orchestration.aggregate_result
    return AskResponse(
        run_id=result.run_id,
        task_id=result.task_id,
        created_message_id=result.created_message_id,
        final_answer=aggregate_result.payload.final_answer,
        source_refs=[
            source_ref.model_dump(mode="json")
            for source_ref in aggregate_result.payload.source_refs
        ],
        aggregate_result=message_to_dict(aggregate_result),
        evaluations=[
            record.model_dump(mode="json") for record in result.orchestration.evaluations
        ],
        executions=[
            record.model_dump(mode="json") for record in result.orchestration.executions
        ],
        run_path=f"/runs/{result.run_id}",
        events_path=f"/runs/{result.run_id}/events",
    )


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
    return cast(CoordinatorStore, store)


def _get_trusted_participants(request: Request) -> dict[ParticipantId, TrustedParticipantConfig]:
    """Return the configured trusted participant registry."""
    trusted_participants = getattr(request.app.state, "trusted_participants", None)
    if trusted_participants is None:
        raise RuntimeError("Coordinator trusted participant registry is not configured.")
    return trusted_participants

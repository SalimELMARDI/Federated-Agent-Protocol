"""Participant discovery routes for the coordinator service."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, Request, status

from coordinator_api.service.discovery import (
    InvalidParticipantDiscoveryResponseError,
    ParticipantDiscoveryIdentityMismatchError,
    ParticipantDiscoveryTransportError,
    discover_participants,
    discovery_result_to_dict,
)
from coordinator_api.service.dispatch import TrustedParticipantRegistry

router = APIRouter()


@router.get("/participants/discovery")
async def list_participant_discovery(request: Request) -> dict[str, object]:
    """Return canonical profile and status metadata for trusted participants."""
    try:
        discovery = await discover_participants(_get_trusted_participants(request))
    except ParticipantDiscoveryIdentityMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_identity_mismatch", "message": str(exc)},
        ) from exc
    except ParticipantDiscoveryTransportError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "participant_discovery_failed", "message": str(exc)},
        ) from exc
    except InvalidParticipantDiscoveryResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "invalid_participant_discovery", "message": str(exc)},
        ) from exc

    return {
        "participant_count": len(discovery),
        "participants": [discovery_result_to_dict(result) for result in discovery],
    }


def _get_trusted_participants(request: Request) -> TrustedParticipantRegistry:
    """Return the configured trusted participant registry."""
    trusted_participants = getattr(request.app.state, "trusted_participants", None)
    if trusted_participants is None:
        raise RuntimeError("Coordinator trusted participant registry is not configured.")
    return cast(TrustedParticipantRegistry, trusted_participants)

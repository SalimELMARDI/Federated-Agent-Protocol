"""Health endpoints for the participant docs service."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Return a minimal health response."""
    return {"status": "ok", "service": "participant_docs"}

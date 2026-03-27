"""Health endpoints for the participant_llm service."""

from fastapi import APIRouter

from participant_llm.config import get_llm_model, get_llm_provider

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Return a minimal health response."""
    return {
        "status": "ok",
        "service": "participant_llm",
        "provider": get_llm_provider(),
        "model": get_llm_model(),
    }

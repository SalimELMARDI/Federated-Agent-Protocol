"""Health endpoints for the participant_llm service."""

from typing import Any

from fastapi import APIRouter

from participant_llm.config import get_llm_model, get_llm_provider, is_participant_llm_enabled

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, Any]:
    """Return a minimal health response with trust model info."""
    return {
        "status": "ok",
        "service": "participant_llm",
        "provider": get_llm_provider(),
        "model": get_llm_model(),
        "enabled": is_participant_llm_enabled(),
        "trust_model": {
            "governance_limitation": "input_queries_sent_ungoverned_to_external_llm",
            "governed_layer": "llm_response_only",
            "acknowledgment_required": "PARTICIPANT_LLM_ENABLE=true",
        },
    }

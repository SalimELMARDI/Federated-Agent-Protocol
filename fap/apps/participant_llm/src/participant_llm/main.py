"""FastAPI entrypoint for the participant_llm service."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI

from participant_llm.api.evaluate import router as evaluate_router
from participant_llm.api.execute import router as execute_router
from participant_llm.api.health import router as health_router
from participant_llm.api.messages import router as messages_router
from participant_llm.api.profile import router as profile_router
from participant_llm.api.status import router as status_router
from participant_llm.config import (
    TRUST_MODEL_WARNING,
    get_llm_model,
    get_llm_provider,
    is_participant_llm_enabled,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _participant_llm_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Verify trust-model acknowledgment before serving requests."""
    del app
    if not is_participant_llm_enabled():
        logger.error(TRUST_MODEL_WARNING)
        logger.error(
            "participant_llm is NOT enabled. Set PARTICIPANT_LLM_ENABLE=true "
            "to acknowledge the trust model and start the service."
        )
        raise RuntimeError(
            "participant_llm requires PARTICIPANT_LLM_ENABLE=true before startup."
        )

    logger.warning(
        "participant_llm is ENABLED. Raw input queries will be sent to external "
        "LLM provider (%s) BEFORE governance is applied. Ensure compliance with "
        "your organization's data policies.",
        get_llm_provider(),
    )
    yield


def create_app() -> FastAPI:
    """Create the participant_llm application."""
    app = FastAPI(title="FAP Participant LLM API", lifespan=_participant_llm_lifespan)
    app.state.llm_provider = get_llm_provider()
    app.state.llm_model = get_llm_model()

    app.include_router(health_router)
    app.include_router(profile_router)
    app.include_router(status_router)
    app.include_router(messages_router)
    app.include_router(evaluate_router)
    app.include_router(execute_router)
    return app


app = create_app()

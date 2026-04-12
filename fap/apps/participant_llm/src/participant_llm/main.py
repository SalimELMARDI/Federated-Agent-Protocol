"""FastAPI entrypoint for the participant_llm service."""

import logging
import sys

from fastapi import FastAPI

from participant_llm.api.evaluate import router as evaluate_router
from participant_llm.api.execute import router as execute_router
from participant_llm.api.health import router as health_router
from participant_llm.api.messages import router as messages_router
from participant_llm.config import (
    TRUST_MODEL_WARNING,
    get_llm_model,
    get_llm_provider,
    is_participant_llm_enabled,
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create the participant_llm application."""
    app = FastAPI(title="FAP Participant LLM API")
    app.state.llm_provider = get_llm_provider()
    app.state.llm_model = get_llm_model()

    @app.on_event("startup")
    async def check_trust_model_acknowledgment() -> None:
        """Verify that the operator has acknowledged the trust model before starting."""
        if not is_participant_llm_enabled():
            logger.error(TRUST_MODEL_WARNING)
            logger.error(
                "participant_llm is NOT enabled. Set PARTICIPANT_LLM_ENABLE=true "
                "to acknowledge the trust model and start the service."
            )
            sys.exit(1)

        logger.warning(
            "participant_llm is ENABLED. Raw input queries will be sent to external "
            "LLM provider (%s) BEFORE governance is applied. Ensure compliance with "
            "your organization's data policies.",
            get_llm_provider(),
        )

    app.include_router(health_router)
    app.include_router(messages_router)
    app.include_router(evaluate_router)
    app.include_router(execute_router)
    return app


app = create_app()

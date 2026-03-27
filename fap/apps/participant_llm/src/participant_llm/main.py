"""FastAPI entrypoint for the participant_llm service."""

from fastapi import FastAPI

from participant_llm.api.evaluate import router as evaluate_router
from participant_llm.api.execute import router as execute_router
from participant_llm.api.health import router as health_router
from participant_llm.api.messages import router as messages_router
from participant_llm.config import get_llm_model, get_llm_provider


def create_app() -> FastAPI:
    """Create the participant_llm application."""
    app = FastAPI(title="FAP Participant LLM API")
    app.state.llm_provider = get_llm_provider()
    app.state.llm_model = get_llm_model()
    app.include_router(health_router)
    app.include_router(messages_router)
    app.include_router(evaluate_router)
    app.include_router(execute_router)
    return app


app = create_app()

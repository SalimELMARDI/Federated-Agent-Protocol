"""FastAPI entrypoint for the participant docs service."""

from fastapi import FastAPI

from participant_docs.adapters.local_docs import load_docs
from participant_docs.api.execute import router as execute_router
from participant_docs.api.evaluate import router as evaluate_router
from participant_docs.api.health import router as health_router
from participant_docs.api.messages import router as messages_router
from participant_docs.api.profile import router as profile_router
from participant_docs.api.status import router as status_router
from participant_docs.config import get_docs_data_dir


def create_app() -> FastAPI:
    """Create the participant docs application."""
    resolved_docs_dir = get_docs_data_dir()
    load_docs(resolved_docs_dir)

    app = FastAPI(title="FAP Participant Docs API")
    app.state.docs_data_dir = resolved_docs_dir
    app.include_router(health_router)
    app.include_router(profile_router)
    app.include_router(status_router)
    app.include_router(messages_router)
    app.include_router(evaluate_router)
    app.include_router(execute_router)
    return app


app = create_app()

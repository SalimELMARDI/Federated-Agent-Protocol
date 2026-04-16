"""FastAPI entrypoint for the participant knowledge-base service."""

from fastapi import FastAPI

from participant_kb.adapters.local_kb import load_kb_entries
from participant_kb.api.evaluate import router as evaluate_router
from participant_kb.api.execute import router as execute_router
from participant_kb.api.health import router as health_router
from participant_kb.api.messages import router as messages_router
from participant_kb.api.profile import router as profile_router
from participant_kb.api.status import router as status_router
from participant_kb.config import get_kb_data_dir


def create_app() -> FastAPI:
    """Create the participant knowledge-base application."""
    resolved_kb_dir = get_kb_data_dir()
    load_kb_entries(resolved_kb_dir)

    app = FastAPI(title="FAP Participant Knowledge Base API")
    app.state.kb_data_dir = resolved_kb_dir
    app.include_router(health_router)
    app.include_router(profile_router)
    app.include_router(status_router)
    app.include_router(messages_router)
    app.include_router(evaluate_router)
    app.include_router(execute_router)
    return app


app = create_app()

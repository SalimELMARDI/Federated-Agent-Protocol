"""FastAPI entrypoint for the participant logs service."""

from fastapi import FastAPI

from participant_logs.adapters.local_logs import load_logs
from participant_logs.api.evaluate import router as evaluate_router
from participant_logs.api.execute import router as execute_router
from participant_logs.api.health import router as health_router
from participant_logs.api.messages import router as messages_router
from participant_logs.api.profile import router as profile_router
from participant_logs.api.status import router as status_router
from participant_logs.config import get_logs_data_dir


def create_app() -> FastAPI:
    """Create the participant logs application."""
    resolved_logs_dir = get_logs_data_dir()
    load_logs(resolved_logs_dir)

    app = FastAPI(title="FAP Participant Logs API")
    app.state.logs_data_dir = resolved_logs_dir
    app.include_router(health_router)
    app.include_router(profile_router)
    app.include_router(status_router)
    app.include_router(messages_router)
    app.include_router(evaluate_router)
    app.include_router(execute_router)
    return app


app = create_app()

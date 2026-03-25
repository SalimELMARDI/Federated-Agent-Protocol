"""FastAPI entrypoint for the coordinator service."""

import httpx
from fastapi import FastAPI

from coordinator_api.api.aggregate import router as aggregate_router
from coordinator_api.api.ask import router as ask_router
from coordinator_api.api.dispatch import router as dispatch_router
from coordinator_api.api.health import router as health_router
from coordinator_api.api.messages import router as messages_router
from coordinator_api.api.orchestrate import router as orchestrate_router
from coordinator_api.api.runs import router as runs_router
from coordinator_api.db import create_session_factory, create_sqlalchemy_engine, init_db
from coordinator_api.service.dispatch import build_trusted_participant_registry
from coordinator_api.service.persistence import CoordinatorPersistenceService, PersistenceService
from coordinator_api.service.store import DatabaseBackedRunStore


def create_app(
    *,
    participant_docs_evaluate_url: str = "http://participant-docs/evaluate",
    participant_docs_execute_url: str = "http://participant-docs/execute",
    participant_docs_transport: httpx.AsyncBaseTransport | None = None,
    participant_kb_evaluate_url: str = "http://participant-kb/evaluate",
    participant_kb_execute_url: str = "http://participant-kb/execute",
    participant_kb_transport: httpx.AsyncBaseTransport | None = None,
    participant_logs_evaluate_url: str = "http://participant-logs/evaluate",
    participant_logs_execute_url: str = "http://participant-logs/execute",
    participant_logs_transport: httpx.AsyncBaseTransport | None = None,
    database_url: str | None = None,
    persistence_service: PersistenceService | None = None,
) -> FastAPI:
    """Create the coordinator API application."""
    app = FastAPI(title="FAP Coordinator API")
    app.state.participant_docs_evaluate_url = participant_docs_evaluate_url
    app.state.participant_docs_execute_url = participant_docs_execute_url
    app.state.participant_docs_transport = participant_docs_transport
    app.state.participant_kb_evaluate_url = participant_kb_evaluate_url
    app.state.participant_kb_execute_url = participant_kb_execute_url
    app.state.participant_kb_transport = participant_kb_transport
    app.state.participant_logs_evaluate_url = participant_logs_evaluate_url
    app.state.participant_logs_execute_url = participant_logs_execute_url
    app.state.participant_logs_transport = participant_logs_transport
    app.state.trusted_participants = build_trusted_participant_registry(
        participant_docs_evaluate_url=participant_docs_evaluate_url,
        participant_docs_execute_url=participant_docs_execute_url,
        participant_docs_transport=participant_docs_transport,
        participant_kb_evaluate_url=participant_kb_evaluate_url,
        participant_kb_execute_url=participant_kb_execute_url,
        participant_kb_transport=participant_kb_transport,
        participant_logs_evaluate_url=participant_logs_evaluate_url,
        participant_logs_execute_url=participant_logs_execute_url,
        participant_logs_transport=participant_logs_transport,
    )
    if persistence_service is None:
        engine = create_sqlalchemy_engine(database_url)
        init_db(engine)
        persistence_service = CoordinatorPersistenceService(create_session_factory(engine))
    app.state.persistence_service = persistence_service
    app.state.run_store = DatabaseBackedRunStore(persistence_service)
    app.include_router(health_router)
    app.include_router(ask_router)
    app.include_router(messages_router)
    app.include_router(runs_router)
    app.include_router(dispatch_router)
    app.include_router(aggregate_router)
    app.include_router(orchestrate_router)
    return app


app = create_app()

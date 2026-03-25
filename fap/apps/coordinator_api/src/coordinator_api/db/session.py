"""Database session helpers for coordinator runtime persistence."""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from coordinator_api.db.models import Base

DEFAULT_DATABASE_URL = "sqlite:///./fap_coordinator.db"


def get_database_url(database_url: str | None = None) -> str:
    """Return the configured database URL with a SQLite default."""
    if database_url is not None:
        return database_url
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_sqlalchemy_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured coordinator database."""
    resolved_url = get_database_url(database_url)
    connect_args: dict[str, object] = {}
    if resolved_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(resolved_url, connect_args=connect_args)


def create_session_factory(
    engine: Engine | None = None, *, database_url: str | None = None
) -> sessionmaker[Session]:
    """Create a SQLAlchemy session factory bound to the coordinator database."""
    bound_engine = engine if engine is not None else create_sqlalchemy_engine(database_url)
    return sessionmaker(bind=bound_engine, class_=Session, expire_on_commit=False)


engine = create_sqlalchemy_engine()
SessionLocal = create_session_factory(engine)


def init_db(engine: Engine | None = None) -> None:
    """Create coordinator runtime tables for local development and tests."""
    Base.metadata.create_all(bind=engine if engine is not None else globals()["engine"])

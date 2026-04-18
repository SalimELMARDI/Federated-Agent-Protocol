"""Tests for the coordinator participant discovery API."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from coordinator_api.main import create_app as create_coordinator_app
from fap_core import message_from_dict
from fap_core.enums import MessageType
from fap_core.messages import ParticipantProfileMessage, ParticipantStatusMessage
from participant_docs.main import create_app as create_participant_docs_app
from participant_kb.main import create_app as create_participant_kb_app
from participant_llm.config import (
    LLM_MODEL_ENV_VAR,
    LLM_PROVIDER_ENV_VAR,
    PARTICIPANT_LLM_ENABLE_ENV_VAR,
)
from participant_llm.main import create_app as create_participant_llm_app
from participant_logs.main import create_app as create_participant_logs_app


def build_client(
    *,
    database_path: Path,
    participant_docs_app: FastAPI | None = None,
    participant_kb_app: FastAPI | None = None,
    participant_logs_app: FastAPI | None = None,
    participant_llm_app: FastAPI | None = None,
) -> TestClient:
    """Return a coordinator client wired to in-process participant apps."""
    docs_app = create_participant_docs_app() if participant_docs_app is None else participant_docs_app
    kb_app = create_participant_kb_app() if participant_kb_app is None else participant_kb_app
    logs_app = create_participant_logs_app() if participant_logs_app is None else participant_logs_app
    llm_app = participant_llm_app
    llm_transport = None if llm_app is None else httpx.ASGITransport(app=llm_app)
    return TestClient(
        create_coordinator_app(
            participant_docs_transport=httpx.ASGITransport(app=docs_app),
            participant_kb_transport=httpx.ASGITransport(app=kb_app),
            participant_logs_transport=httpx.ASGITransport(app=logs_app),
            participant_llm_evaluate_url=(
                None if llm_app is None else "http://participant-llm/evaluate"
            ),
            participant_llm_execute_url=(
                None if llm_app is None else "http://participant-llm/execute"
            ),
            participant_llm_transport=llm_transport,
            database_url=f"sqlite:///{database_path.as_posix()}",
        )
    )


def test_participant_discovery_lists_all_trusted_participants(tmp_path: Path) -> None:
    """The coordinator should expose profile and status metadata for each trusted participant."""
    client = build_client(database_path=tmp_path / "coordinator.db")

    response = client.get("/participants/discovery")

    assert response.status_code == 200
    body = response.json()
    assert body["participant_count"] == 3
    assert [entry["participant_id"] for entry in body["participants"]] == [
        "participant_docs",
        "participant_kb",
        "participant_logs",
    ]

    for entry in body["participants"]:
        profile = message_from_dict(entry["profile"])
        status = message_from_dict(entry["status"])
        assert isinstance(profile, ParticipantProfileMessage)
        assert isinstance(status, ParticipantStatusMessage)
        assert profile.envelope.message_type == MessageType.FAP_PARTICIPANT_PROFILE
        assert status.envelope.message_type == MessageType.FAP_PARTICIPANT_STATUS
        assert profile.payload.participant_id == entry["participant_id"]
        assert status.payload.participant_id == entry["participant_id"]


def test_participant_discovery_surfaces_unreachable_participants(tmp_path: Path) -> None:
    """Transport or routing failures during discovery should surface clearly."""
    client = build_client(
        database_path=tmp_path / "coordinator.db",
        participant_docs_app=FastAPI(),
    )

    response = client.get("/participants/discovery")

    assert response.status_code == 502
    assert response.json() == {
        "detail": {
            "code": "participant_discovery_failed",
            "message": "participant_docs discovery failed with status 404",
        }
    }


def test_participant_discovery_includes_llm_when_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The coordinator should surface participant_llm discovery metadata when configured."""
    monkeypatch.setenv(PARTICIPANT_LLM_ENABLE_ENV_VAR, "true")
    monkeypatch.setenv(LLM_PROVIDER_ENV_VAR, "anthropic")
    monkeypatch.setenv(LLM_MODEL_ENV_VAR, "test-llm-model")

    client = build_client(
        database_path=tmp_path / "coordinator-llm.db",
        participant_llm_app=create_participant_llm_app(),
    )

    response = client.get("/participants/discovery")

    assert response.status_code == 200
    body = response.json()
    assert body["participant_count"] == 4
    assert [entry["participant_id"] for entry in body["participants"]] == [
        "participant_docs",
        "participant_kb",
        "participant_logs",
        "participant_llm",
    ]

    llm_entry = body["participants"][-1]
    profile = message_from_dict(llm_entry["profile"])
    status = message_from_dict(llm_entry["status"])
    assert isinstance(profile, ParticipantProfileMessage)
    assert isinstance(status, ParticipantStatusMessage)
    assert profile.payload.participant_id == "participant_llm"
    assert profile.payload.execution_class.value == "outbound"
    assert profile.payload.outbound_network_access is True
    assert status.payload.participant_id == "participant_llm"
    assert status.payload.accepting_tasks is True

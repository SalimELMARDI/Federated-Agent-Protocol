"""Tests for participant discovery profile/status endpoints."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fap_core import message_from_dict
from fap_core.enums import (
    MessageType,
    ParticipantExecutionClass,
    ParticipantHealth,
    ParticipantLatencyClass,
)
from fap_core.messages import ParticipantProfileMessage, ParticipantStatusMessage
from participant_docs.main import create_app as create_participant_docs_app
from participant_kb.main import create_app as create_participant_kb_app
from participant_logs.main import create_app as create_participant_logs_app


@pytest.mark.parametrize(
    ("app_factory", "participant_id", "capability_prefix"),
    [
        (create_participant_docs_app, "participant_docs", "docs."),
        (create_participant_kb_app, "participant_kb", "kb."),
        (create_participant_logs_app, "participant_logs", "logs."),
    ],
)
def test_profile_endpoint_returns_canonical_profile_message(
    app_factory: Callable[[], FastAPI],
    participant_id: str,
    capability_prefix: str,
) -> None:
    """Each participant should expose a canonical profile message."""
    client = TestClient(app_factory())

    response = client.get("/profile")

    assert response.status_code == 200
    parsed = message_from_dict(response.json())
    assert isinstance(parsed, ParticipantProfileMessage)
    assert parsed.envelope.message_type == MessageType.FAP_PARTICIPANT_PROFILE
    assert parsed.envelope.sender_id == participant_id
    assert parsed.envelope.recipient_id == "coordinator"
    assert parsed.payload.participant_id == participant_id
    assert parsed.payload.domain_id == participant_id
    assert parsed.payload.execution_class == ParticipantExecutionClass.LOCAL
    assert parsed.payload.latency_class == ParticipantLatencyClass.INTERACTIVE
    assert parsed.payload.supports_mcp is False
    assert parsed.payload.outbound_network_access is False
    assert parsed.payload.capabilities
    assert all(capability.startswith(capability_prefix) for capability in parsed.payload.capabilities)


@pytest.mark.parametrize(
    ("app_factory", "participant_id", "capability_prefix"),
    [
        (create_participant_docs_app, "participant_docs", "docs."),
        (create_participant_kb_app, "participant_kb", "kb."),
        (create_participant_logs_app, "participant_logs", "logs."),
    ],
)
def test_status_endpoint_returns_canonical_status_message(
    app_factory: Callable[[], FastAPI],
    participant_id: str,
    capability_prefix: str,
) -> None:
    """Each participant should expose a canonical status message."""
    client = TestClient(app_factory())

    response = client.get("/status")

    assert response.status_code == 200
    parsed = message_from_dict(response.json())
    assert isinstance(parsed, ParticipantStatusMessage)
    assert parsed.envelope.message_type == MessageType.FAP_PARTICIPANT_STATUS
    assert parsed.envelope.sender_id == participant_id
    assert parsed.envelope.recipient_id == "coordinator"
    assert parsed.payload.participant_id == participant_id
    assert parsed.payload.domain_id == participant_id
    assert parsed.payload.health == ParticipantHealth.OK
    assert parsed.payload.accepting_tasks is True
    assert parsed.payload.load == 0
    assert parsed.payload.available_capabilities
    assert all(
        capability.startswith(capability_prefix)
        for capability in parsed.payload.available_capabilities
    )

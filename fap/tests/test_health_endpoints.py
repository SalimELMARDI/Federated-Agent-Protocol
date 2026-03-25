"""Smoke tests for the scaffolded FastAPI apps."""

from __future__ import annotations

from importlib import import_module

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    ("module_name", "service_name"),
    [
        ("coordinator_api.main", "coordinator_api"),
        ("participant_docs.main", "participant_docs"),
        ("participant_logs.main", "participant_logs"),
        ("participant_kb.main", "participant_kb"),
    ],
)
def test_health_endpoint(module_name: str, service_name: str) -> None:
    """Each scaffolded service should expose a minimal health route."""
    module = import_module(module_name)
    client = TestClient(module.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": service_name}

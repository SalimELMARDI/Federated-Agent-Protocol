"""Minimal external Python client for the FAP coordinator runtime."""

from fap_client.client import FAPClient, FAPClientError, FAPClientHTTPError, FAPClientResponseError
from fap_client.models import (
    AskResponse,
    EvaluationRecord,
    ExecutionRecord,
    PersistedEventSummary,
    RunEventsResponse,
    RunSnapshotResponse,
    SourceRefResponse,
)

__version__ = "0.1.0a0"

__all__ = [
    "AskResponse",
    "EvaluationRecord",
    "ExecutionRecord",
    "FAPClient",
    "FAPClientError",
    "FAPClientHTTPError",
    "FAPClientResponseError",
    "PersistedEventSummary",
    "RunEventsResponse",
    "RunSnapshotResponse",
    "SourceRefResponse",
    "__version__",
]

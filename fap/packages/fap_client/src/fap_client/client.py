"""Minimal external Python client for the FAP coordinator runtime."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from fap_client.models import AskResponse, RunEventsResponse, RunSnapshotResponse


class FAPClientError(Exception):
    """Base exception for FAP client failures."""


class FAPClientHTTPError(FAPClientError):
    """Raised when the coordinator returns an unexpected HTTP status."""

    def __init__(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        detail: object | None,
    ) -> None:
        self.method = method
        self.path = path
        self.status_code = status_code
        self.detail = detail
        super().__init__(
            f"FAP coordinator request failed: {method} {path} -> {status_code}"
        )


class FAPClientResponseError(FAPClientError):
    """Raised when a coordinator response is not valid JSON or has the wrong shape."""


class FAPClient:
    """Thin reusable client for the FAP coordinator runtime."""

    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client if client is not None else httpx.Client(timeout=timeout)

    def close(self) -> None:
        """Close the underlying HTTP client if this instance created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> FAPClient:
        """Enter a context-managed client session."""
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Close owned resources when leaving a context-managed session."""
        del exc_type, exc, tb
        self.close()

    def ask(self, question: str) -> AskResponse:
        """Submit a plain-language question through the coordinator `/ask` capability."""
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must be a non-empty string")

        payload = self._request_json(
            "POST",
            "/ask",
            expected_statuses={200},
            json={"query": normalized_question},
        )
        if not isinstance(payload, dict):
            raise FAPClientResponseError("Expected object JSON response from /ask")

        return AskResponse.model_validate(payload)

    def get_run(self, run_id: str) -> RunSnapshotResponse:
        """Fetch the latest coordinator run snapshot for a run id."""
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            raise ValueError("run_id must be a non-empty string")

        payload = self._request_json(
            "GET",
            f"/runs/{normalized_run_id}",
            expected_statuses={200},
        )
        if not isinstance(payload, dict):
            raise FAPClientResponseError("Expected object JSON response from /runs/{run_id}")

        return RunSnapshotResponse.model_validate(payload)

    def get_events(self, run_id: str) -> RunEventsResponse:
        """Fetch persisted coordinator event summaries for a run id."""
        normalized_run_id = run_id.strip()
        if not normalized_run_id:
            raise ValueError("run_id must be a non-empty string")

        payload = self._request_json(
            "GET",
            f"/runs/{normalized_run_id}/events",
            expected_statuses={200},
        )
        if not isinstance(payload, list):
            raise FAPClientResponseError("Expected list JSON response from /runs/{run_id}/events")

        return RunEventsResponse.model_validate(
            {
                "run_id": normalized_run_id,
                "events": payload,
            }
        )

    def submit_message(self, message: Mapping[str, object]) -> dict[str, object]:
        """Submit canonical FAP wire data directly to the coordinator `/messages` ingress."""
        payload = self._request_json(
            "POST",
            "/messages",
            expected_statuses={202},
            json=dict(message),
        )
        if not isinstance(payload, dict):
            raise FAPClientResponseError("Expected object JSON response from /messages")
        return payload

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        expected_statuses: set[int],
        json: Mapping[str, object] | None = None,
    ) -> Any:
        """Perform an HTTP request and decode the coordinator JSON response."""
        url = f"{self._base_url}{path}"
        try:
            response = self._client.request(method, url, json=json)
        except httpx.HTTPError as exc:
            raise FAPClientError(f"FAP coordinator request failed: {method} {path}: {exc}") from exc

        detail: object | None
        try:
            detail = response.json()
        except ValueError:
            detail = response.text

        if response.status_code not in expected_statuses:
            raise FAPClientHTTPError(
                method=method,
                path=path,
                status_code=response.status_code,
                detail=detail,
            )

        if isinstance(detail, str):
            raise FAPClientResponseError(
                f"Expected JSON response body from {method} {path}"
            )

        return detail

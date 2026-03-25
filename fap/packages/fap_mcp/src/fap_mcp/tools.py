"""MCP tool handlers built on top of the external FAP Python client."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from fap_client import AskResponse, FAPClient, RunEventsResponse, RunSnapshotResponse


class FAPClientProtocol(Protocol):
    """Protocol describing the FAP client surface needed by the MCP wrapper."""

    def ask(self, question: str) -> AskResponse:
        """Run a federated question through the FAP coordinator."""

    def get_run(self, run_id: str) -> RunSnapshotResponse:
        """Fetch the latest run snapshot from the coordinator."""

    def get_events(self, run_id: str) -> RunEventsResponse:
        """Fetch persisted event summaries from the coordinator."""

    def submit_message(self, message: Mapping[str, object]) -> dict[str, object]:
        """Submit canonical FAP wire data to the coordinator."""


@dataclass(slots=True)
class FAPMCPToolHandlers:
    """Thin MCP-facing tool handlers that delegate to ``fap_client``."""

    client: FAPClientProtocol

    def fap_ask(self, question: str) -> dict[str, Any]:
        """Expose the coordinator `/ask` capability as an MCP tool."""
        return self.client.ask(question).model_dump(mode="json")

    def fap_get_run(self, run_id: str) -> dict[str, Any]:
        """Expose coordinator run inspection as an MCP tool."""
        return self.client.get_run(run_id).model_dump(mode="json")

    def fap_get_events(self, run_id: str) -> dict[str, Any]:
        """Expose persisted event inspection as an MCP tool."""
        events = self.client.get_events(run_id)
        return {
            "run_id": events.run_id,
            "events": [event.model_dump(mode="json") for event in events.events],
        }

    def fap_submit_message(self, message: Mapping[str, object]) -> dict[str, object]:
        """Expose raw canonical message submission for experimentation."""
        return self.client.submit_message(message)


def build_tool_handlers(client: FAPClient | FAPClientProtocol) -> FAPMCPToolHandlers:
    """Build the MCP tool handler set for the given FAP client."""
    return FAPMCPToolHandlers(client=client)

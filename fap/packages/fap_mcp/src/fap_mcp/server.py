"""Minimal MCP server wrapper exposing the FAP coordinator as tools."""

from __future__ import annotations

from typing import Any

from fap_client import FAPClient
from mcp.server.fastmcp import FastMCP

from fap_mcp.tools import FAPClientProtocol, build_tool_handlers

DEFAULT_COORDINATOR_URL = "http://127.0.0.1:8011"


def create_fap_mcp_server(
    *,
    base_url: str = DEFAULT_COORDINATOR_URL,
    client: FAPClient | FAPClientProtocol | None = None,
    host: str = "127.0.0.1",
    port: int = 8015,
) -> FastMCP:
    """Create a small MCP server that exposes the FAP coordinator runtime."""
    resolved_client = client if client is not None else FAPClient(base_url)
    handlers = build_tool_handlers(resolved_client)

    server = FastMCP(
        name="fap-mcp",
        instructions=(
            "Use these tools to ask federated questions through the FAP coordinator, "
            "inspect run snapshots, and inspect persisted event history."
        ),
        host=host,
        port=port,
        dependencies=["fap", "mcp"],
    )

    @server.tool(
        name="fap_ask",
        description="Ask a federated question through the FAP coordinator `/ask` capability.",
    )
    def fap_ask(question: str) -> dict[str, Any]:
        return handlers.fap_ask(question)

    @server.tool(
        name="fap_get_run",
        description="Inspect the latest coordinator run snapshot for a run id.",
    )
    def fap_get_run(run_id: str) -> dict[str, Any]:
        return handlers.fap_get_run(run_id)

    @server.tool(
        name="fap_get_events",
        description="Inspect persisted coordinator event summaries for a run id.",
    )
    def fap_get_events(run_id: str) -> dict[str, Any]:
        return handlers.fap_get_events(run_id)

    @server.tool(
        name="fap_submit_message",
        description="Submit a canonical FAP wire message directly to the coordinator ingress.",
    )
    def fap_submit_message(message: dict[str, object]) -> dict[str, object]:
        return handlers.fap_submit_message(message)

    return server

"""Minimal MCP server wrapper for exposing the FAP coordinator as tools."""

from fap_mcp.server import DEFAULT_COORDINATOR_URL, create_fap_mcp_server
from fap_mcp.tools import FAPClientProtocol, FAPMCPToolHandlers, build_tool_handlers

__version__ = "0.1.0a0"

__all__ = [
    "DEFAULT_COORDINATOR_URL",
    "FAPClientProtocol",
    "FAPMCPToolHandlers",
    "__version__",
    "build_tool_handlers",
    "create_fap_mcp_server",
]

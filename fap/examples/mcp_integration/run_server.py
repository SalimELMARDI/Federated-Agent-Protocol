"""Run the minimal FAP MCP server wrapper."""

from __future__ import annotations

import argparse
import os

from fap_mcp import DEFAULT_COORDINATOR_URL, create_fap_mcp_server


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI parser for the MCP wrapper example."""
    parser = argparse.ArgumentParser(description="Run the FAP MCP server wrapper")
    parser.add_argument(
        "--coordinator-url",
        default=os.getenv("FAP_COORDINATOR_URL", DEFAULT_COORDINATOR_URL),
        help="Base URL for the running FAP coordinator.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
        help="MCP transport to serve.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host for HTTP transports.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8015,
        help="Bind port for HTTP transports.",
    )
    return parser


def main() -> int:
    """Run the MCP server with the configured transport."""
    args = build_parser().parse_args()
    server = create_fap_mcp_server(
        base_url=args.coordinator_url,
        host=args.host,
        port=args.port,
    )
    server.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

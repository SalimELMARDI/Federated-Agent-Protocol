"""Artifact checks for the minimal MCP integration example."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = ROOT / "examples" / "mcp_integration"


def test_required_mcp_integration_files_exist() -> None:
    """The MCP integration example should ship with the required files."""
    required_paths = [
        EXAMPLE_DIR / "README.md",
        EXAMPLE_DIR / "run_server.py",
    ]

    for path in required_paths:
        assert path.exists(), f"Missing MCP integration artifact: {path}"


def test_run_server_script_is_syntactically_valid() -> None:
    """The MCP example script should parse successfully as Python."""
    source = (EXAMPLE_DIR / "run_server.py").read_text(encoding="utf-8")
    ast.parse(source, filename=str(EXAMPLE_DIR / "run_server.py"))

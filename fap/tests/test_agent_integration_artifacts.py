"""Artifact checks for the minimal external agent integration example."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = ROOT / "examples" / "agent_integration"


def test_required_agent_integration_files_exist() -> None:
    """The agent integration example should ship with the required files."""
    required_paths = [
        EXAMPLE_DIR / "README.md",
        EXAMPLE_DIR / "simple_agent.py",
    ]

    for path in required_paths:
        assert path.exists(), f"Missing agent integration artifact: {path}"


def test_simple_agent_script_is_syntactically_valid() -> None:
    """The agent example should parse successfully as Python."""
    source = (EXAMPLE_DIR / "simple_agent.py").read_text(encoding="utf-8")
    ast.parse(source, filename=str(EXAMPLE_DIR / "simple_agent.py"))

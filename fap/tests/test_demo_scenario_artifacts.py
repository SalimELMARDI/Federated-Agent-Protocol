"""Artifact checks for the release demo scenario."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "examples" / "demo_scenario"


def test_required_demo_files_exist() -> None:
    """The demo scenario should ship with the required versioned artifacts."""
    required_paths = [
        DEMO_DIR / "README.md",
        DEMO_DIR / "create_task.json",
        DEMO_DIR / "run_demo.py",
        DEMO_DIR / "expected_flow.md",
        ROOT / "Makefile",
    ]

    for path in required_paths:
        assert path.exists(), f"Missing demo artifact: {path}"


def test_create_task_json_is_valid_and_has_canonical_top_level_shape() -> None:
    """The demo input JSON should be valid and use the canonical envelope/payload structure."""
    with (DEMO_DIR / "create_task.json").open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    assert isinstance(data, dict)
    assert "envelope" in data
    assert "payload" in data
    assert isinstance(data["envelope"], dict)
    assert isinstance(data["payload"], dict)
    assert data["envelope"]["message_type"] == "fap.task.create"


def test_run_demo_script_is_syntactically_valid() -> None:
    """The demo runner should at least parse successfully as Python."""
    source = (DEMO_DIR / "run_demo.py").read_text(encoding="utf-8")
    ast.parse(source, filename=str(DEMO_DIR / "run_demo.py"))

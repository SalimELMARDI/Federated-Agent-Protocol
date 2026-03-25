"""Lightweight release-readiness checks for the first public alpha."""

from __future__ import annotations

from pathlib import Path
import tomllib

import fap_client
import fap_core
import fap_mcp


ROOT = Path(__file__).resolve().parents[1]


def test_release_artifact_files_exist() -> None:
    """Release-facing docs and metadata files should exist."""
    required_paths = [
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "LICENSE",
        ROOT / "docs" / "release-checklist.md",
        ROOT / "docs" / "release-notes" / "v0.1.0-alpha.md",
    ]

    assert all(path.exists() for path in required_paths)


def test_pyproject_runtime_dependencies_match_the_actual_alpha_surface() -> None:
    """Core dependencies should not advertise unused runtime substrate or dev-only tools."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    dependencies = set(project["dependencies"])
    dev_dependencies = set(project["optional-dependencies"]["dev"])

    assert "flwr" not in dependencies
    assert "structlog" not in dependencies
    assert "orjson" not in dependencies
    assert "pydantic-settings" not in dependencies

    assert "pytest" not in dependencies
    assert "pytest-asyncio" not in dependencies
    assert "ruff" not in dependencies
    assert "mypy" not in dependencies

    assert {"pytest", "pytest-asyncio", "ruff", "mypy"} <= dev_dependencies


def test_release_readme_positions_the_repo_honestly() -> None:
    """The landing page should state the alpha scope and package layout clearly."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()

    assert "v0.1.0-alpha" in readme
    assert "protocol alpha" in readme
    assert "reference runtime" in readme
    assert "developer preview" in readme
    assert "not yet production stable" in readme or "not production stable" in readme
    assert "fap_core" in readme
    assert "fap_client" in readme
    assert "fap_mcp" in readme


def test_release_docs_do_not_contain_local_absolute_machine_paths() -> None:
    """Release-facing markdown should not leak local workstation paths."""
    release_docs = [
        ROOT / "README.md",
        ROOT / "examples" / "demo_scenario" / "README.md",
        ROOT / "examples" / "agent_integration" / "README.md",
        ROOT / "examples" / "mcp_integration" / "README.md",
    ]

    for path in release_docs:
        text = path.read_text(encoding="utf-8")
        assert "C:/Users/elmar" not in text
        assert "c:/Users/elmar" not in text
        assert "C:\\Users\\elmar" not in text
        assert "c:\\Users\\elmar" not in text


def test_primary_import_packages_are_importable_for_release() -> None:
    """The main published import surfaces should import cleanly."""
    assert fap_core.__version__ == "0.1.0a0"
    assert fap_client.__version__ == "0.1.0a0"
    assert fap_mcp.__version__ == "0.1.0a0"

"""Tests for the participant_kb local knowledge-base adapter."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest import MonkeyPatch

from participant_kb.adapters.local_kb import (
    DEFAULT_KB_DATA_DIR,
    KB_PATH_ENV_VAR,
    get_kb_data_dir,
    load_kb_entries,
    search_kb,
)
from participant_kb.main import create_app


def test_default_kb_directory_contains_seeded_entries() -> None:
    """The default participant-local KB directory should load the seeded entries."""
    entries = load_kb_entries()

    assert get_kb_data_dir() == DEFAULT_KB_DATA_DIR
    assert [entry.entry_id for entry in entries] == [
        "kb-001",
        "kb-002",
        "kb-003",
        "kb-004",
        "kb-005",
    ]
    assert [entry.topic for entry in entries] == [
        "Privacy controls",
        "Incident facts",
        "Summary Guidance",
        "Knowledge lookup",
        "Retention Practices",
    ]


def test_load_and_search_support_json_markdown_and_text_entries(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The local KB connector should load multiple file formats deterministically."""
    (tmp_path / "kb-010__release-roadmap.txt").write_text(
        "Roadmap notes for staged release planning.\n",
        encoding="utf-8",
    )
    (tmp_path / "kb-020__incident-facts.md").write_text(
        "# Incident facts\n\nFact records for response timelines.\n",
        encoding="utf-8",
    )
    (tmp_path / "kb-030__privacy-controls.json").write_text(
        (
            '{\n'
            '  "entry_id": "kb-030",\n'
            '  "topic": "Privacy controls",\n'
            '  "content": "Controls for privacy review and governed sharing."\n'
            '}\n'
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(KB_PATH_ENV_VAR, str(tmp_path))

    entries = load_kb_entries()
    matches = search_kb("facts")

    assert [entry.entry_id for entry in entries] == ["kb-010", "kb-020", "kb-030"]
    assert entries[0].source_path.endswith("kb-010__release-roadmap.txt")
    assert entries[1].topic == "Incident facts"
    assert entries[2].topic == "Privacy controls"
    assert [entry.entry_id for entry in matches] == ["kb-020"]


def test_search_is_case_insensitive_and_stable(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Searching a custom KB source should preserve deterministic filename order."""
    (tmp_path / "kb-010__alpha-summary.txt").write_text(
        "Summary guidance for local KB reviews.\n",
        encoding="utf-8",
    )
    (tmp_path / "kb-020__beta-summary.txt").write_text(
        "Summary notes for post-incident reviews.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(KB_PATH_ENV_VAR, str(tmp_path))

    matches = search_kb("SUMMARY")

    assert [entry.entry_id for entry in matches] == ["kb-010", "kb-020"]
    assert [entry.topic for entry in matches] == ["Alpha Summary", "Beta Summary"]


def test_no_match_returns_empty_results(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """A configured KB directory should still return empty results when nothing matches."""
    (tmp_path / "kb-010__incident-facts.md").write_text(
        "# Incident facts\n\nStructured incident timeline notes.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(KB_PATH_ENV_VAR, str(tmp_path))

    assert search_kb("privacy") == []


def test_invalid_kb_path_fails_clearly_on_load(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """A missing KB directory should raise a clear load-time error."""
    missing_dir = tmp_path / "missing-kb"
    monkeypatch.setenv(KB_PATH_ENV_VAR, str(missing_dir))

    with pytest.raises(FileNotFoundError, match="participant_kb data directory does not exist"):
        load_kb_entries()


def test_invalid_kb_path_fails_clearly_at_app_startup(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The participant app should fail early if its configured KB directory is invalid."""
    missing_dir = tmp_path / "missing-kb"
    monkeypatch.setenv(KB_PATH_ENV_VAR, str(missing_dir))

    with pytest.raises(FileNotFoundError, match="participant_kb data directory does not exist"):
        create_app()

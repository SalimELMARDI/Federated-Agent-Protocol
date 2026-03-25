"""Tests for the participant_logs local logs adapter."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest import MonkeyPatch

from participant_logs.adapters.local_logs import (
    DEFAULT_LOGS_DATA_DIR,
    LOGS_PATH_ENV_VAR,
    get_logs_data_dir,
    load_logs,
    search_logs,
)
from participant_logs.main import create_app


def test_default_logs_directory_contains_seeded_events() -> None:
    """The default participant-local logs directory should load the seeded events."""
    events = load_logs()

    assert get_logs_data_dir() == DEFAULT_LOGS_DATA_DIR
    assert [event.event_id for event in events] == [
        "log-001",
        "log-002",
        "log-003",
        "log-004",
        "log-005",
    ]
    assert [event.source for event in events] == [
        "auth-service",
        "privacy-monitor",
        "search-worker",
        "incident-pipeline",
        "release-audit",
    ]


def test_load_and_search_support_json_log_text_and_markdown_entries(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The local logs connector should load multiple file formats deterministically."""
    (tmp_path / "log-010__alpha.json").write_text(
        (
            '{\n'
            '  "event_id": "log-010",\n'
            '  "source": "alpha-monitor",\n'
            '  "message": "Privacy event recorded for local review.",\n'
            '  "level": "info"\n'
            '}\n'
        ),
        encoding="utf-8",
    )
    (tmp_path / "log-020__beta-worker.log").write_text(
        "WARN beta worker checkpoint stored for replay.\n",
        encoding="utf-8",
    )
    (tmp_path / "log-030__gamma-service.txt").write_text(
        "Gamma service info message for local review.\n",
        encoding="utf-8",
    )
    (tmp_path / "log-040__delta-audit.md").write_text(
        "Delta audit checkpoint for release review.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(LOGS_PATH_ENV_VAR, str(tmp_path))

    events = load_logs()
    matches = search_logs("replay")

    assert [event.event_id for event in events] == ["log-010", "log-020", "log-030", "log-040"]
    assert events[0].source_path.endswith("log-010__alpha.json")
    assert events[1].source == "beta-worker"
    assert events[1].level == "warn"
    assert events[2].level == "info"
    assert events[3].source == "delta-audit"
    assert [event.event_id for event in matches] == ["log-020"]


def test_search_logs_matches_case_insensitively_in_stable_order(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Searching a custom local logs source should preserve deterministic order."""
    (tmp_path / "log-010__alpha-monitor.log").write_text(
        "INFO alpha monitor summary checkpoint.\n",
        encoding="utf-8",
    )
    (tmp_path / "log-020__beta-worker.txt").write_text(
        "Summary event retained for worker review.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(LOGS_PATH_ENV_VAR, str(tmp_path))

    matches = search_logs("SUMMARY")

    assert [event.event_id for event in matches] == ["log-010", "log-020"]
    assert [event.source for event in matches] == ["alpha-monitor", "beta-worker"]


def test_no_match_returns_empty_results(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """A configured logs directory should still return empty results when nothing matches."""
    (tmp_path / "log-010__incident-pipeline.log").write_text(
        "INFO incident pipeline replay checkpoint recorded.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(LOGS_PATH_ENV_VAR, str(tmp_path))

    assert search_logs("privacy") == []


def test_invalid_logs_path_fails_clearly_on_load(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """A missing logs directory should raise a clear load-time error."""
    missing_dir = tmp_path / "missing-logs"
    monkeypatch.setenv(LOGS_PATH_ENV_VAR, str(missing_dir))

    with pytest.raises(FileNotFoundError, match="participant_logs data directory does not exist"):
        load_logs()


def test_invalid_logs_path_fails_clearly_at_app_startup(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The participant app should fail early if its configured logs directory is invalid."""
    missing_dir = tmp_path / "missing-logs"
    monkeypatch.setenv(LOGS_PATH_ENV_VAR, str(missing_dir))

    with pytest.raises(FileNotFoundError, match="participant_logs data directory does not exist"):
        create_app()

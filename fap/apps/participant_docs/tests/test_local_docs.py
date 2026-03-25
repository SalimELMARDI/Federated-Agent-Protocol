"""Tests for the participant_docs local docs adapter."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest import MonkeyPatch

from participant_docs.adapters.local_docs import (
    DEFAULT_DOCS_DATA_DIR,
    DOCS_PATH_ENV_VAR,
    get_docs_data_dir,
    load_docs,
    search_docs,
)
from participant_docs.main import create_app


def test_default_docs_directory_contains_seeded_docs() -> None:
    """The default participant-local docs directory should load the seeded docs."""
    docs = load_docs()

    assert get_docs_data_dir() == DEFAULT_DOCS_DATA_DIR
    assert [doc.doc_id for doc in docs] == [
        "doc-001",
        "doc-002",
        "doc-003",
        "doc-004",
        "doc-005",
    ]
    assert [doc.title for doc in docs] == [
        "Incident Response Handbook",
        "Privacy Policy Memo",
        "Quarterly Summary",
        "Lookup Runbook",
        "Release Notes",
    ]


def test_load_and_search_support_markdown_text_and_json_documents(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The local docs connector should load multiple file formats deterministically."""
    (tmp_path / "doc-010__alpha-brief.txt").write_text(
        "Alpha brief for staged local review.\n",
        encoding="utf-8",
    )
    (tmp_path / "doc-020__beta-incident.md").write_text(
        "# Beta Incident\n\nIncident notes for coordinated review.\n",
        encoding="utf-8",
    )
    (tmp_path / "doc-030__privacy-memo.json").write_text(
        (
            '{\n'
            '  "doc_id": "doc-030",\n'
            '  "title": "Privacy Memo",\n'
            '  "content": "Privacy evidence for governed local review."\n'
            '}\n'
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(DOCS_PATH_ENV_VAR, str(tmp_path))

    docs = load_docs()
    matches = search_docs("privacy")

    assert [doc.doc_id for doc in docs] == ["doc-010", "doc-020", "doc-030"]
    assert docs[0].source_path.endswith("doc-010__alpha-brief.txt")
    assert docs[1].title == "Beta Incident"
    assert docs[2].title == "Privacy Memo"
    assert [doc.doc_id for doc in matches] == ["doc-030"]


def test_search_docs_matches_case_insensitively_in_stable_order(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """Searching a custom docs source should preserve deterministic filename order."""
    (tmp_path / "doc-010__alpha-summary.txt").write_text(
        "Summary evidence for local reporting.\n",
        encoding="utf-8",
    )
    (tmp_path / "doc-020__beta-summary.txt").write_text(
        "Summary notes for staged local review.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(DOCS_PATH_ENV_VAR, str(tmp_path))

    matches = search_docs("SUMMARY")

    assert [doc.doc_id for doc in matches] == ["doc-010", "doc-020"]
    assert [doc.title for doc in matches] == ["Alpha Summary", "Beta Summary"]


def test_no_match_returns_empty_results(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """A configured docs directory should still return empty results when nothing matches."""
    (tmp_path / "doc-010__incident-notes.md").write_text(
        "# Incident Notes\n\nStructured incident response review material.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(DOCS_PATH_ENV_VAR, str(tmp_path))

    assert search_docs("privacy") == []


def test_invalid_docs_path_fails_clearly_on_load(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """A missing docs directory should raise a clear load-time error."""
    missing_dir = tmp_path / "missing-docs"
    monkeypatch.setenv(DOCS_PATH_ENV_VAR, str(missing_dir))

    with pytest.raises(FileNotFoundError, match="participant_docs data directory does not exist"):
        load_docs()


def test_invalid_docs_path_fails_clearly_at_app_startup(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """The participant app should fail early if its configured docs directory is invalid."""
    missing_dir = tmp_path / "missing-docs"
    monkeypatch.setenv(DOCS_PATH_ENV_VAR, str(missing_dir))

    with pytest.raises(FileNotFoundError, match="participant_docs data directory does not exist"):
        create_app()

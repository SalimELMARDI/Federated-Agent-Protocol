"""Filesystem-backed local knowledge-base source for participant_kb."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from participant_kb.config import DEFAULT_KB_DATA_DIR, KB_PATH_ENV_VAR, get_kb_data_dir

SUPPORTED_KB_FILE_SUFFIXES = (".json", ".md", ".txt")


class LocalKBEntry(BaseModel):
    """A participant-local knowledge-base entry loaded from disk."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str
    topic: str
    content: str
    source_path: str


class _LocalKBJSONPayload(BaseModel):
    """Simple JSON payload shape supported by the local KB connector."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str
    topic: str
    content: str


def validate_kb_data_dir(kb_dir: Path | None = None) -> Path:
    """Return the resolved KB directory or raise a clear startup/load error."""
    resolved_dir = kb_dir if kb_dir is not None else get_kb_data_dir()
    if not resolved_dir.exists():
        raise FileNotFoundError(
            f"participant_kb data directory does not exist: {resolved_dir}"
        )
    if not resolved_dir.is_dir():
        raise NotADirectoryError(
            f"participant_kb data directory is not a directory: {resolved_dir}"
        )
    return resolved_dir


def load_kb_entries(kb_dir: Path | None = None) -> list[LocalKBEntry]:
    """Load participant-local KB entries from the configured directory."""
    resolved_dir = validate_kb_data_dir(kb_dir)
    supported_paths = [
        entry_path
        for entry_path in sorted(resolved_dir.iterdir())
        if entry_path.is_file() and entry_path.suffix.lower() in SUPPORTED_KB_FILE_SUFFIXES
    ]
    return [_parse_kb_entry(entry_path) for entry_path in supported_paths]


def search_kb(query: str, kb_dir: Path | None = None) -> list[LocalKBEntry]:
    """Return local KB entries whose topic or content contains the query."""
    normalized_query = query.casefold()
    return [
        entry
        for entry in load_kb_entries(kb_dir)
        if normalized_query in entry.topic.casefold()
        or normalized_query in entry.content.casefold()
    ]


def _parse_kb_entry(entry_path: Path) -> LocalKBEntry:
    """Parse one supported KB file into a canonical LocalKBEntry."""
    suffix = entry_path.suffix.lower()
    if suffix == ".json":
        return _parse_json_entry(entry_path)
    return _parse_text_entry(entry_path)


def _parse_json_entry(entry_path: Path) -> LocalKBEntry:
    """Parse a JSON knowledge-base entry."""
    payload = json.loads(entry_path.read_text(encoding="utf-8"))
    parsed = _LocalKBJSONPayload.model_validate(payload)
    return LocalKBEntry(
        entry_id=parsed.entry_id,
        topic=parsed.topic,
        content=parsed.content,
        source_path=str(entry_path),
    )


def _parse_text_entry(entry_path: Path) -> LocalKBEntry:
    """Parse a markdown or text knowledge-base entry."""
    raw_text = entry_path.read_text(encoding="utf-8").strip()
    lines = raw_text.splitlines()
    topic = _derive_topic(entry_path, lines)
    content = _derive_content(entry_path, raw_text, lines)
    entry_id, _, _ = entry_path.stem.partition("__")
    return LocalKBEntry(
        entry_id=entry_id or entry_path.stem,
        topic=topic,
        content=content,
        source_path=str(entry_path),
    )


def _derive_topic(entry_path: Path, lines: list[str]) -> str:
    """Derive a stable topic from the file heading or filename."""
    if entry_path.suffix.lower() == ".md":
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith("# "):
                return stripped_line[2:].strip()

    _, _, fallback_topic = entry_path.stem.partition("__")
    normalized_topic = fallback_topic.replace("-", " ").replace("_", " ").strip()
    return normalized_topic.title() or entry_path.stem


def _derive_content(entry_path: Path, raw_text: str, lines: list[str]) -> str:
    """Derive the content body from a text or markdown entry."""
    if entry_path.suffix.lower() == ".md":
        for index, line in enumerate(lines):
            stripped_line = line.strip()
            if stripped_line.startswith("# "):
                remaining_text = "\n".join(lines[index + 1 :]).strip()
                return remaining_text or stripped_line[2:].strip()
    return raw_text


__all__ = [
    "DEFAULT_KB_DATA_DIR",
    "KB_PATH_ENV_VAR",
    "LocalKBEntry",
    "SUPPORTED_KB_FILE_SUFFIXES",
    "get_kb_data_dir",
    "load_kb_entries",
    "search_kb",
    "validate_kb_data_dir",
]

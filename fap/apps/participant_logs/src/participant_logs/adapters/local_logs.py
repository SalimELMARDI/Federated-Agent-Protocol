"""Filesystem-backed local log source for participant_logs."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from participant_logs.config import DEFAULT_LOGS_DATA_DIR, LOGS_PATH_ENV_VAR, get_logs_data_dir

SUPPORTED_LOG_FILE_SUFFIXES = (".json", ".log", ".txt", ".md")


class LocalLogEvent(BaseModel):
    """A participant-local log event record loaded from disk."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    source: str
    message: str
    level: str
    source_path: str


class _LocalLogJSONPayload(BaseModel):
    """Simple JSON payload shape supported by the local logs connector."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    source: str
    message: str
    level: str


def validate_logs_data_dir(logs_dir: Path | None = None) -> Path:
    """Return the resolved logs directory or raise a clear startup/load error."""
    resolved_dir = logs_dir if logs_dir is not None else get_logs_data_dir()
    if not resolved_dir.exists():
        raise FileNotFoundError(
            f"participant_logs data directory does not exist: {resolved_dir}"
        )
    if not resolved_dir.is_dir():
        raise NotADirectoryError(
            f"participant_logs data directory is not a directory: {resolved_dir}"
        )
    return resolved_dir


def load_logs(logs_dir: Path | None = None) -> list[LocalLogEvent]:
    """Load participant-local log events from the configured logs directory."""
    resolved_dir = validate_logs_data_dir(logs_dir)
    supported_paths = [
        log_path
        for log_path in sorted(resolved_dir.iterdir())
        if log_path.is_file() and log_path.suffix.lower() in SUPPORTED_LOG_FILE_SUFFIXES
    ]
    return [_parse_log_file(log_path) for log_path in supported_paths]


def search_logs(query: str, logs_dir: Path | None = None) -> list[LocalLogEvent]:
    """Return local log events whose source or message contains the query."""
    normalized_query = query.casefold()
    return [
        event
        for event in load_logs(logs_dir)
        if normalized_query in event.source.casefold()
        or normalized_query in event.message.casefold()
    ]


def _parse_log_file(log_path: Path) -> LocalLogEvent:
    """Parse one supported log file into a canonical LocalLogEvent."""
    suffix = log_path.suffix.lower()
    if suffix == ".json":
        return _parse_json_event(log_path)
    return _parse_text_event(log_path)


def _parse_json_event(log_path: Path) -> LocalLogEvent:
    """Parse a JSON log file."""
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    parsed = _LocalLogJSONPayload.model_validate(payload)
    return LocalLogEvent(
        event_id=parsed.event_id,
        source=parsed.source,
        message=parsed.message,
        level=parsed.level,
        source_path=str(log_path),
    )


def _parse_text_event(log_path: Path) -> LocalLogEvent:
    """Parse a text, markdown, or .log file into a single stable event."""
    raw_text = log_path.read_text(encoding="utf-8").strip()
    source = _derive_source(log_path)
    event_id, _, _ = log_path.stem.partition("__")
    return LocalLogEvent(
        event_id=event_id or log_path.stem,
        source=source,
        message=raw_text,
        level=_infer_level(raw_text),
        source_path=str(log_path),
    )


def _derive_source(log_path: Path) -> str:
    """Derive a stable source identifier from the filename."""
    _, _, fallback_source = log_path.stem.partition("__")
    normalized_source = fallback_source.replace("_", "-").strip()
    return normalized_source or log_path.stem


def _infer_level(message: str) -> str:
    """Infer a simple deterministic log level from the file content."""
    normalized_message = message.casefold()
    if "error" in normalized_message:
        return "error"
    if "warn" in normalized_message or "warning" in normalized_message:
        return "warn"
    if "debug" in normalized_message:
        return "debug"
    return "info"


__all__ = [
    "DEFAULT_LOGS_DATA_DIR",
    "LOGS_PATH_ENV_VAR",
    "LocalLogEvent",
    "SUPPORTED_LOG_FILE_SUFFIXES",
    "get_logs_data_dir",
    "load_logs",
    "search_logs",
    "validate_logs_data_dir",
]

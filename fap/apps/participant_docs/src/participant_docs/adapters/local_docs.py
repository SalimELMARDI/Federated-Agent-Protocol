"""Filesystem-backed local document source for participant_docs."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from participant_docs.config import DEFAULT_DOCS_DATA_DIR, DOCS_PATH_ENV_VAR, get_docs_data_dir

SUPPORTED_DOC_FILE_SUFFIXES = (".json", ".md", ".txt")


class LocalDoc(BaseModel):
    """A participant-local document record loaded from disk."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    content: str
    source_path: str


class _LocalDocJSONPayload(BaseModel):
    """Simple JSON payload shape supported by the local docs connector."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str
    title: str
    content: str


def validate_docs_data_dir(docs_dir: Path | None = None) -> Path:
    """Return the resolved docs directory or raise a clear startup/load error."""
    resolved_dir = docs_dir if docs_dir is not None else get_docs_data_dir()
    if not resolved_dir.exists():
        raise FileNotFoundError(
            f"participant_docs data directory does not exist: {resolved_dir}"
        )
    if not resolved_dir.is_dir():
        raise NotADirectoryError(
            f"participant_docs data directory is not a directory: {resolved_dir}"
        )
    return resolved_dir


def load_docs(docs_dir: Path | None = None) -> list[LocalDoc]:
    """Load participant-local documents from the configured docs directory."""
    resolved_dir = validate_docs_data_dir(docs_dir)
    supported_paths = [
        doc_path
        for doc_path in sorted(resolved_dir.iterdir())
        if doc_path.is_file() and doc_path.suffix.lower() in SUPPORTED_DOC_FILE_SUFFIXES
    ]
    return [_parse_doc_file(doc_path) for doc_path in supported_paths]


def search_docs(query: str, docs_dir: Path | None = None) -> list[LocalDoc]:
    """Return local documents whose title or content contains the query."""
    normalized_query = query.casefold()
    return [
        doc
        for doc in load_docs(docs_dir)
        if normalized_query in doc.title.casefold() or normalized_query in doc.content.casefold()
    ]


def _parse_doc_file(doc_path: Path) -> LocalDoc:
    """Parse one supported document file into a canonical LocalDoc."""
    suffix = doc_path.suffix.lower()
    if suffix == ".json":
        return _parse_json_doc(doc_path)
    return _parse_text_doc(doc_path)


def _parse_json_doc(doc_path: Path) -> LocalDoc:
    """Parse a JSON document entry."""
    payload = json.loads(doc_path.read_text(encoding="utf-8"))
    parsed = _LocalDocJSONPayload.model_validate(payload)
    return LocalDoc(
        doc_id=parsed.doc_id,
        title=parsed.title,
        content=parsed.content,
        source_path=str(doc_path),
    )


def _parse_text_doc(doc_path: Path) -> LocalDoc:
    """Parse a markdown or text document entry."""
    raw_text = doc_path.read_text(encoding="utf-8").strip()
    lines = raw_text.splitlines()
    title = _derive_title(doc_path, lines)
    content = _derive_content(doc_path, raw_text, lines)
    doc_id, _, _ = doc_path.stem.partition("__")
    return LocalDoc(
        doc_id=doc_id or doc_path.stem,
        title=title,
        content=content,
        source_path=str(doc_path),
    )


def _derive_title(doc_path: Path, lines: list[str]) -> str:
    """Derive a stable title from the heading or filename."""
    if doc_path.suffix.lower() == ".md":
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith("# "):
                return stripped_line[2:].strip()

    _, _, fallback_title = doc_path.stem.partition("__")
    normalized_title = fallback_title.replace("-", " ").replace("_", " ").strip()
    return normalized_title.title() or doc_path.stem


def _derive_content(doc_path: Path, raw_text: str, lines: list[str]) -> str:
    """Derive the content body from a markdown or text document entry."""
    if doc_path.suffix.lower() == ".md":
        for index, line in enumerate(lines):
            stripped_line = line.strip()
            if stripped_line.startswith("# "):
                remaining_text = "\n".join(lines[index + 1 :]).strip()
                return remaining_text or stripped_line[2:].strip()
    return raw_text


__all__ = [
    "DEFAULT_DOCS_DATA_DIR",
    "DOCS_PATH_ENV_VAR",
    "LocalDoc",
    "SUPPORTED_DOC_FILE_SUFFIXES",
    "get_docs_data_dir",
    "load_docs",
    "search_docs",
    "validate_docs_data_dir",
]

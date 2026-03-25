"""Configuration helpers for the participant_docs local connector."""

from __future__ import annotations

import os
from pathlib import Path

DOCS_PATH_ENV_VAR = "PARTICIPANT_DOCS_PATH"
DEFAULT_DOCS_DATA_DIR = Path(__file__).resolve().parents[4] / "examples" / "local_docs" / "data"


def get_docs_data_dir() -> Path:
    """Return the configured participant-local document directory."""
    configured_path = os.getenv(DOCS_PATH_ENV_VAR)
    if configured_path:
        return Path(configured_path).expanduser()
    return DEFAULT_DOCS_DATA_DIR

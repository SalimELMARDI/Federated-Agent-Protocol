"""Configuration helpers for the participant_kb local connector."""

from __future__ import annotations

import os
from pathlib import Path

KB_PATH_ENV_VAR = "PARTICIPANT_KB_PATH"
DEFAULT_KB_DATA_DIR = Path(__file__).resolve().parents[4] / "examples" / "local_kb" / "data"


def get_kb_data_dir() -> Path:
    """Return the configured participant-local knowledge-base directory."""
    configured_path = os.getenv(KB_PATH_ENV_VAR)
    if configured_path:
        return Path(configured_path).expanduser()
    return DEFAULT_KB_DATA_DIR

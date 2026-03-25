"""Configuration helpers for the participant_logs local connector."""

from __future__ import annotations

import os
from pathlib import Path

LOGS_PATH_ENV_VAR = "PARTICIPANT_LOGS_PATH"
DEFAULT_LOGS_DATA_DIR = Path(__file__).resolve().parents[4] / "examples" / "local_logs" / "data"


def get_logs_data_dir() -> Path:
    """Return the configured participant-local logs directory."""
    configured_path = os.getenv(LOGS_PATH_ENV_VAR)
    if configured_path:
        return Path(configured_path).expanduser()
    return DEFAULT_LOGS_DATA_DIR

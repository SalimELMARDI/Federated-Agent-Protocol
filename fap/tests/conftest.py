"""Shared test configuration for the FAP scaffold."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIRS = [
    ROOT / "apps" / "coordinator_api" / "src",
    ROOT / "apps" / "participant_docs" / "src",
    ROOT / "apps" / "participant_logs" / "src",
    ROOT / "apps" / "participant_kb" / "src",
    ROOT / "packages" / "fap_client" / "src",
    ROOT / "packages" / "fap_mcp" / "src",
    ROOT / "packages" / "fap_core" / "src",
]

for src_dir in SRC_DIRS:
    src_path = str(src_dir)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

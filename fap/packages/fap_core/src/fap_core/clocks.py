"""Clock helpers for FAP timestamps."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)

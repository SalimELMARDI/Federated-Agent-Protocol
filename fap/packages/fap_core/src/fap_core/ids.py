"""ID helpers for common FAP identifiers."""

from uuid import uuid4


def _new_prefixed_id(prefix: str) -> str:
    """Return a UUID4-backed identifier with a stable prefix."""
    return f"{prefix}_{uuid4().hex}"


def new_message_id() -> str:
    """Return a new message identifier."""
    return _new_prefixed_id("msg")


def new_task_id() -> str:
    """Return a new task identifier."""
    return _new_prefixed_id("task")


def new_run_id() -> str:
    """Return a new run identifier."""
    return _new_prefixed_id("run")


def new_trace_id() -> str:
    """Return a new trace identifier."""
    return _new_prefixed_id("trace")

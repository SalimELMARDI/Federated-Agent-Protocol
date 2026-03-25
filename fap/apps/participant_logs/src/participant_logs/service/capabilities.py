"""Capability profile for the participant_logs service."""

SUPPORTED_CAPABILITIES: tuple[str, ...] = (
    "logs.search",
    "logs.events",
    "logs.summarize",
)


def get_supported_capabilities() -> tuple[str, ...]:
    """Return the supported participant_logs capability set."""
    return SUPPORTED_CAPABILITIES

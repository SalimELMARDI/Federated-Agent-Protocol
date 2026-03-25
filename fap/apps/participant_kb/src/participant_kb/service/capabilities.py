"""Capability profile for the participant_kb service."""

SUPPORTED_CAPABILITIES: tuple[str, ...] = (
    "kb.lookup",
    "kb.facts",
    "kb.summarize",
)


def get_supported_capabilities() -> tuple[str, ...]:
    """Return the supported participant_kb capability set."""
    return SUPPORTED_CAPABILITIES

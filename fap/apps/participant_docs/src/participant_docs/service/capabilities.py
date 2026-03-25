"""Capability profile for the participant docs service."""

SUPPORTED_CAPABILITIES: tuple[str, ...] = (
    "docs.search",
    "docs.lookup",
    "docs.summarize",
)


def get_supported_capabilities() -> tuple[str, ...]:
    """Return the supported participant_docs capability set."""
    return SUPPORTED_CAPABILITIES

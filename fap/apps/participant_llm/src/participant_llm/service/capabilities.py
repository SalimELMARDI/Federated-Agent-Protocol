"""Capability profile for the participant_llm service."""

SUPPORTED_CAPABILITIES: tuple[str, ...] = (
    "llm.query",
    "llm.summarize",
    "llm.reason",
)


def get_supported_capabilities() -> tuple[str, ...]:
    """Return the supported participant_llm capability set."""
    return SUPPORTED_CAPABILITIES

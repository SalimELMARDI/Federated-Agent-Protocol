"""Configuration helpers for the participant_llm LLM connector."""

from __future__ import annotations

import os

LLM_PROVIDER_ENV_VAR = "LLM_PROVIDER"
LLM_MODEL_ENV_VAR = "LLM_MODEL"
LLM_API_KEY_ENV_VAR = "LLM_API_KEY"
LLM_BASE_URL_ENV_VAR = "LLM_BASE_URL"
PARTICIPANT_LLM_ENABLE_ENV_VAR = "PARTICIPANT_LLM_ENABLE"

DEFAULT_LLM_PROVIDER = "anthropic"
DEFAULT_LLM_MODEL = "claude-sonnet-4-20250514"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434/v1"

SUPPORTED_PROVIDERS = ("anthropic", "openai", "ollama")

# Trust model warning for participant_llm
TRUST_MODEL_WARNING = """
╔════════════════════════════════════════════════════════════════════════════╗
║                    PARTICIPANT_LLM TRUST MODEL WARNING                     ║
╚════════════════════════════════════════════════════════════════════════════╝

This participant sends raw input queries to external LLM providers BEFORE
governance is applied. This differs from FAP's core "policy before export"
principle for file-backed participants.

⚠️  GOVERNANCE LIMITATION:
   • Input queries are transmitted to external APIs UNGOVERNED
   • Only LLM responses are governed before returning to coordinator
   • Raw queries may contain sensitive data (PII, credentials, proprietary info)

✓  SAFE TO ENABLE IF:
   • Queries do not contain sensitive or regulated data
   • External LLM provider is trusted and compliant
   • Privacy/compliance requirements allow external transmission
   • You accept the input-query governance gap

❌  DO NOT ENABLE IF:
   • Queries may contain PII, PHI, financial data, or trade secrets
   • Compliance requires data locality (GDPR, HIPAA, SOC2)
   • Zero-trust policy prohibits ungoverned external transmission

To acknowledge this trust model and enable the participant, set:
    PARTICIPANT_LLM_ENABLE=true

For more details, see fap/apps/participant_llm/README.md § Trust Model
"""


def get_llm_provider() -> str:
    """Return the configured LLM provider."""
    return os.getenv(LLM_PROVIDER_ENV_VAR, DEFAULT_LLM_PROVIDER).lower()


def get_llm_model() -> str:
    """Return the configured LLM model name."""
    return os.getenv(LLM_MODEL_ENV_VAR, DEFAULT_LLM_MODEL)


def get_llm_api_key() -> str:
    """Return the configured LLM API key."""
    return os.getenv(LLM_API_KEY_ENV_VAR, "")


def get_llm_base_url() -> str:
    """Return the configured LLM base URL, applying provider-specific defaults."""
    configured = os.getenv(LLM_BASE_URL_ENV_VAR, "")
    if configured:
        return configured.rstrip("/")
    provider = get_llm_provider()
    if provider == "ollama":
        return OLLAMA_DEFAULT_BASE_URL
    return OPENAI_DEFAULT_BASE_URL


def is_participant_llm_enabled() -> bool:
    """Check if participant_llm is explicitly enabled via environment variable."""
    return os.getenv(PARTICIPANT_LLM_ENABLE_ENV_VAR, "").lower() in ("true", "1", "yes")

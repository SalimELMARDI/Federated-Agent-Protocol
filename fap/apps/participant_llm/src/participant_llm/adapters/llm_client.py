"""LLM HTTP adapter for participant_llm — supports Anthropic and OpenAI-compatible endpoints."""

from __future__ import annotations

import httpx

from participant_llm.config import (
    ANTHROPIC_API_URL,
    ANTHROPIC_VERSION,
    get_llm_api_key,
    get_llm_base_url,
    get_llm_model,
    get_llm_provider,
)


class LLMCallError(Exception):
    """Raised when the LLM API call fails."""


class LLMResponse:
    """Minimal result returned by the LLM adapter."""

    def __init__(self, content: str, model: str, endpoint_url: str) -> None:
        self.content = content
        self.model = model
        self.endpoint_url = endpoint_url


async def call_llm(query: str) -> LLMResponse:
    """Send a query to the configured LLM and return the response text.

    Uses async HTTP client to avoid blocking the event loop in async FastAPI context.
    """
    provider = get_llm_provider()
    model = get_llm_model()
    api_key = get_llm_api_key()

    if provider == "anthropic":
        return await _call_anthropic(query, model=model, api_key=api_key)
    if provider in ("openai", "ollama"):
        return await _call_openai_compatible(query, model=model, api_key=api_key)

    raise LLMCallError(
        f"Unsupported LLM provider: {provider!r}. "
        "Supported providers: anthropic, openai, ollama"
    )


async def _call_anthropic(query: str, *, model: str, api_key: str) -> LLMResponse:
    """Call the Anthropic Messages API using async HTTP client."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": query}],
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(ANTHROPIC_API_URL, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise LLMCallError(f"Anthropic API request failed: {exc}") from exc

    if response.status_code != 200:
        raise LLMCallError(
            f"Anthropic API returned status {response.status_code}: {response.text[:200]}"
        )

    try:
        data = response.json()
        content = data["content"][0]["text"]
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMCallError(f"Unexpected Anthropic API response shape: {exc}") from exc

    return LLMResponse(content=content, model=model, endpoint_url=ANTHROPIC_API_URL)


async def _call_openai_compatible(query: str, *, model: str, api_key: str) -> LLMResponse:
    """Call an OpenAI-compatible chat completions endpoint using async HTTP client."""
    base_url = get_llm_base_url()
    endpoint_url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "messages": [{"role": "user", "content": query}],
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint_url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise LLMCallError(f"OpenAI-compatible API request failed: {exc}") from exc

    if response.status_code != 200:
        raise LLMCallError(
            f"OpenAI-compatible API returned status {response.status_code}: {response.text[:200]}"
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMCallError(f"Unexpected OpenAI-compatible API response shape: {exc}") from exc

    return LLMResponse(content=content, model=model, endpoint_url=endpoint_url)


__all__ = ["LLMCallError", "LLMResponse", "call_llm"]

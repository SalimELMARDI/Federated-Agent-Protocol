"""Transport-independent codec helpers for canonical FAP wire data."""

from __future__ import annotations

import json
from typing import Any, cast

from fap_core.messages import SupportedMessage
from fap_core.messages.registry import parse_message


class MessageCodecError(Exception):
    """Base error for FAP codec failures."""


class MessageJsonDecodeError(MessageCodecError):
    """Raised when JSON text cannot be decoded."""


class MessageJsonShapeError(MessageCodecError):
    """Raised when decoded JSON does not have the expected object shape."""


def message_to_dict(message: SupportedMessage) -> dict[str, object]:
    """Serialize a typed message into canonical JSON-safe FAP data."""
    return cast(dict[str, object], message.model_dump(mode="json"))


def message_to_json(message: SupportedMessage) -> str:
    """Serialize a typed message into canonical JSON text."""
    return message.model_dump_json()


def message_from_dict(data: dict[str, object]) -> SupportedMessage:
    """Parse canonical JSON-safe FAP data into a typed message."""
    return parse_message(cast(dict[str, Any], data))


def message_from_json(data: str) -> SupportedMessage:
    """Decode JSON text and parse it into a typed FAP message."""
    try:
        raw = json.loads(data)
    except json.JSONDecodeError as exc:
        raise MessageJsonDecodeError("Invalid JSON message payload.") from exc

    if not isinstance(raw, dict):
        raise MessageJsonShapeError("Top-level JSON value must be an object.")

    return message_from_dict(cast(dict[str, object], raw))

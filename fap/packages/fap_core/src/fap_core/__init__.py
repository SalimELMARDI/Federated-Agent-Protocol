"""Shared FAP package for protocol-level code."""

from fap_core.api_helpers import (
    build_accepted_response,
    parse_inbound_message,
    to_protocol_http_exception,
)
from fap_core.codec import (
    MessageCodecError,
    MessageJsonDecodeError,
    MessageJsonShapeError,
    message_from_dict,
    message_from_json,
    message_to_dict,
    message_to_json,
)
from fap_core.messages import MessageParseError, SupportedMessage, UnknownMessageKindError

__all__ = [
    "build_accepted_response",
    "MessageCodecError",
    "MessageJsonDecodeError",
    "MessageJsonShapeError",
    "MessageParseError",
    "SupportedMessage",
    "UnknownMessageKindError",
    "__version__",
    "parse_inbound_message",
    "message_from_dict",
    "message_from_json",
    "message_to_dict",
    "message_to_json",
    "to_protocol_http_exception",
]

__version__ = "0.1.0a0"

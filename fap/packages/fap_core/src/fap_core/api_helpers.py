"""Shared HTTP-facing helpers for FAP protocol ingress routes."""

from __future__ import annotations

from typing import overload, TypedDict

from fastapi import HTTPException, status

from fap_core.codec import message_from_dict
from fap_core.messages import MessageParseError, SupportedMessage, UnknownMessageKindError


class AcceptedResponsePayload(TypedDict):
    """Canonical accepted response payload for ingress endpoints."""

    status: str
    message_type: str
    message_id: str
    task_id: str
    run_id: str


class AcceptedServiceResponsePayload(AcceptedResponsePayload):
    """Accepted response payload that includes the service name."""

    service: str


def parse_inbound_message(data: dict[str, object]) -> SupportedMessage:
    """Parse canonical inbound FAP data into a typed message."""
    return message_from_dict(data)


def to_protocol_http_exception(exc: Exception) -> HTTPException:
    """Convert shared parser errors into stable HTTP API responses."""
    if isinstance(exc, UnknownMessageKindError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "unsupported_message_kind", "message": str(exc)},
        )

    if isinstance(exc, MessageParseError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_message", "message": str(exc)},
        )

    raise TypeError(f"Unsupported exception type for protocol HTTP mapping: {type(exc).__name__}")


@overload
def build_accepted_response(message: SupportedMessage, *, service: None = None) -> AcceptedResponsePayload:
    ...


@overload
def build_accepted_response(
    message: SupportedMessage, *, service: str
) -> AcceptedServiceResponsePayload:
    ...


def build_accepted_response(
    message: SupportedMessage, *, service: str | None = None
) -> AcceptedResponsePayload | AcceptedServiceResponsePayload:
    """Build the canonical accepted response payload for parsed messages."""
    response: AcceptedResponsePayload = {
        "status": "accepted",
        "message_type": message.envelope.message_type,
        "message_id": message.envelope.message_id,
        "task_id": message.envelope.task_id,
        "run_id": message.envelope.run_id,
    }

    if service is not None:
        return AcceptedServiceResponsePayload(**response, service=service)

    return response

"""Protocol ingress routes for the participant docs service."""

from __future__ import annotations

from fastapi import APIRouter, Body, status
from pydantic import BaseModel, ConfigDict

from fap_core import build_accepted_response, parse_inbound_message, to_protocol_http_exception

router = APIRouter()


class MessageAcceptedResponse(BaseModel):
    """Minimal acceptance response for parsed FAP messages."""

    model_config = ConfigDict(extra="forbid")

    status: str
    message_type: str
    message_id: str
    task_id: str
    run_id: str
    service: str


@router.post("/messages", response_model=MessageAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_message(message: dict[str, object] = Body(...)) -> MessageAcceptedResponse:
    """Accept and parse a raw FAP message without executing participant logic."""
    try:
        parsed = parse_inbound_message(message)
    except Exception as exc:
        raise to_protocol_http_exception(exc) from exc

    return MessageAcceptedResponse(**build_accepted_response(parsed, service="participant_docs"))

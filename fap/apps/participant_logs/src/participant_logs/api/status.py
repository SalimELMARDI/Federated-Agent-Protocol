"""Participant status endpoint for the logs participant."""

from fastapi import APIRouter

from fap_core import message_to_dict
from participant_logs.service.metadata import build_status_message

router = APIRouter()


@router.get("/status")
async def status() -> dict[str, object]:
    """Return the canonical FAP participant status."""
    return message_to_dict(build_status_message())

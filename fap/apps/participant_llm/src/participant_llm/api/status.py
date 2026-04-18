"""Participant status endpoint for the participant_llm service."""

from fastapi import APIRouter

from fap_core import message_to_dict
from participant_llm.service.metadata import build_status_message

router = APIRouter()


@router.get("/status")
async def status() -> dict[str, object]:
    """Return the canonical FAP participant status."""
    return message_to_dict(build_status_message())

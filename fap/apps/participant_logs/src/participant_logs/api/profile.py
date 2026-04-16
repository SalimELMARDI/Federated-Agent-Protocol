"""Participant profile endpoint for the logs participant."""

from fastapi import APIRouter

from fap_core import message_to_dict
from participant_logs.service.metadata import build_profile_message

router = APIRouter()


@router.get("/profile")
async def profile() -> dict[str, object]:
    """Return the canonical FAP participant profile."""
    return message_to_dict(build_profile_message())

"""Participant profile endpoint for the participant_llm service."""

from fastapi import APIRouter

from fap_core import message_to_dict
from participant_llm.service.metadata import build_profile_message

router = APIRouter()


@router.get("/profile")
async def profile() -> dict[str, object]:
    """Return the canonical FAP participant profile."""
    return message_to_dict(build_profile_message())

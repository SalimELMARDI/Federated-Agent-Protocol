"""Shared identity helpers for trusted FAP runtime participants."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Mapping


class CoordinatorId(StrEnum):
    """Canonical coordinator-side runtime identities."""

    COORDINATOR = "coordinator"


class ParticipantId(StrEnum):
    """Canonical trusted participant ids supported by the alpha runtime."""

    PARTICIPANT_DOCS = "participant_docs"
    PARTICIPANT_KB = "participant_kb"
    PARTICIPANT_LOGS = "participant_logs"


@dataclass(frozen=True)
class TrustedParticipantIdentity:
    """Minimal trusted identity record for a known participant."""

    participant_id: ParticipantId
    domain_id: str


COORDINATOR_ID: Final[CoordinatorId] = CoordinatorId.COORDINATOR

TRUSTED_PARTICIPANT_IDENTITIES: Final[Mapping[ParticipantId, TrustedParticipantIdentity]] = (
    MappingProxyType(
        {
            ParticipantId.PARTICIPANT_DOCS: TrustedParticipantIdentity(
                participant_id=ParticipantId.PARTICIPANT_DOCS,
                domain_id=ParticipantId.PARTICIPANT_DOCS.value,
            ),
            ParticipantId.PARTICIPANT_KB: TrustedParticipantIdentity(
                participant_id=ParticipantId.PARTICIPANT_KB,
                domain_id=ParticipantId.PARTICIPANT_KB.value,
            ),
            ParticipantId.PARTICIPANT_LOGS: TrustedParticipantIdentity(
                participant_id=ParticipantId.PARTICIPANT_LOGS,
                domain_id=ParticipantId.PARTICIPANT_LOGS.value,
            ),
        }
    )
)


def get_trusted_participant_identity(
    participant_id: ParticipantId | str,
) -> TrustedParticipantIdentity:
    """Return the canonical trusted identity for a known participant id."""
    normalized_id = (
        participant_id if isinstance(participant_id, ParticipantId) else ParticipantId(participant_id)
    )
    return TRUSTED_PARTICIPANT_IDENTITIES[normalized_id]


def is_known_participant_id(value: str) -> bool:
    """Return whether the given string is a currently trusted participant id."""
    try:
        ParticipantId(value)
    except ValueError:
        return False
    return True


__all__ = [
    "COORDINATOR_ID",
    "CoordinatorId",
    "ParticipantId",
    "TRUSTED_PARTICIPANT_IDENTITIES",
    "TrustedParticipantIdentity",
    "get_trusted_participant_identity",
    "is_known_participant_id",
]

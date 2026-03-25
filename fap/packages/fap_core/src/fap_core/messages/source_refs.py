"""Shared source-reference models for FAP evidence pointers."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class SourceRef(BaseModel):
    """Deterministic pointer to a participant-local source used during execution."""

    model_config = ConfigDict(extra="forbid")

    participant_id: NonEmptyText
    source_id: NonEmptyText
    source_title: NonEmptyText
    source_path: NonEmptyText

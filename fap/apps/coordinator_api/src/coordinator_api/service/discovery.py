"""Coordinator-side participant discovery helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from urllib.parse import urlsplit, urlunsplit

import httpx

from coordinator_api.service.dispatch import TrustedParticipantConfig, TrustedParticipantRegistry
from fap_core import message_from_dict, message_to_dict
from fap_core.messages import (
    MessageParseError,
    ParticipantProfileMessage,
    ParticipantStatusMessage,
    UnknownMessageKindError,
)


class ParticipantDiscoveryTransportError(Exception):
    """Raised when coordinator discovery cannot reach a participant endpoint."""


class InvalidParticipantDiscoveryResponseError(Exception):
    """Raised when a participant discovery endpoint returns invalid data."""


class ParticipantDiscoveryIdentityMismatchError(Exception):
    """Raised when participant discovery metadata does not match trusted identity."""


@dataclass(frozen=True)
class ParticipantDiscoveryResult:
    """Discovery bundle for a trusted participant."""

    participant_id: str
    profile_message: ParticipantProfileMessage
    status_message: ParticipantStatusMessage


async def discover_participants(
    trusted_participants: TrustedParticipantRegistry,
) -> list[ParticipantDiscoveryResult]:
    """Fetch profile and status metadata from every trusted participant."""
    results: list[ParticipantDiscoveryResult] = []
    for config in trusted_participants.values():
        profile_message = await _fetch_profile_message(config)
        status_message = await _fetch_status_message(config)
        results.append(
            ParticipantDiscoveryResult(
                participant_id=config.identity.participant_id.value,
                profile_message=profile_message,
                status_message=status_message,
            )
        )
    return results


def discovery_result_to_dict(result: ParticipantDiscoveryResult) -> dict[str, object]:
    """Serialize one discovery bundle into JSON-safe data."""
    return {
        "participant_id": result.participant_id,
        "profile": message_to_dict(result.profile_message),
        "status": message_to_dict(result.status_message),
    }


async def _fetch_profile_message(
    config: TrustedParticipantConfig,
) -> ParticipantProfileMessage:
    """Fetch and validate a participant profile message."""
    raw = await _fetch_json_message(_derive_companion_endpoint_url(config.evaluate_url, "profile"), config)
    parsed = _parse_discovery_message(raw)
    if not isinstance(parsed, ParticipantProfileMessage):
        raise InvalidParticipantDiscoveryResponseError(
            f"{config.identity.participant_id.value} returned unexpected discovery message type "
            f"{parsed.envelope.message_type.value!r} for /profile"
        )
    _validate_identity(parsed, config=config, endpoint_name="profile")
    return parsed


async def _fetch_status_message(
    config: TrustedParticipantConfig,
) -> ParticipantStatusMessage:
    """Fetch and validate a participant status message."""
    raw = await _fetch_json_message(_derive_companion_endpoint_url(config.evaluate_url, "status"), config)
    parsed = _parse_discovery_message(raw)
    if not isinstance(parsed, ParticipantStatusMessage):
        raise InvalidParticipantDiscoveryResponseError(
            f"{config.identity.participant_id.value} returned unexpected discovery message type "
            f"{parsed.envelope.message_type.value!r} for /status"
        )
    _validate_identity(parsed, config=config, endpoint_name="status")
    return parsed


async def _fetch_json_message(
    url: str,
    config: TrustedParticipantConfig,
) -> dict[str, object]:
    """Fetch one discovery endpoint as canonical message-shaped JSON."""
    participant_name = config.identity.participant_id.value
    try:
        async with httpx.AsyncClient(transport=config.transport) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        raise ParticipantDiscoveryTransportError(
            f"{participant_name} discovery request failed: {exc}"
        ) from exc

    if response.status_code != 200:
        raise ParticipantDiscoveryTransportError(
            f"{participant_name} discovery failed with status {response.status_code}"
        )

    try:
        raw = response.json()
    except ValueError as exc:
        raise InvalidParticipantDiscoveryResponseError(
            f"{participant_name} returned invalid JSON discovery response"
        ) from exc

    if not isinstance(raw, dict):
        raise InvalidParticipantDiscoveryResponseError(
            f"{participant_name} returned non-object JSON discovery response"
        )

    return cast(dict[str, object], raw)


def _parse_discovery_message(
    raw: dict[str, object],
) -> ParticipantProfileMessage | ParticipantStatusMessage:
    """Parse a discovery response through the shared FAP parser."""
    try:
        parsed = message_from_dict(raw)
    except (MessageParseError, UnknownMessageKindError) as exc:
        raise InvalidParticipantDiscoveryResponseError(str(exc)) from exc

    if isinstance(parsed, ParticipantProfileMessage | ParticipantStatusMessage):
        return parsed

    raise InvalidParticipantDiscoveryResponseError(
        f"Unsupported discovery message type: {parsed.envelope.message_type.value!r}"
    )


def _validate_identity(
    message: ParticipantProfileMessage | ParticipantStatusMessage,
    *,
    config: TrustedParticipantConfig,
    endpoint_name: str,
) -> None:
    """Ensure discovery metadata matches the trusted participant identity."""
    expected_sender_id = config.identity.participant_id.value
    expected_domain_id = config.identity.domain_id
    expected_recipient_id = "coordinator"

    if message.envelope.sender_id != expected_sender_id:
        raise ParticipantDiscoveryIdentityMismatchError(
            f"{expected_sender_id} returned /{endpoint_name} sender_id mismatch: expected "
            f"{expected_sender_id!r}, got {message.envelope.sender_id!r}"
        )
    if message.envelope.domain_id != expected_domain_id:
        raise ParticipantDiscoveryIdentityMismatchError(
            f"{expected_sender_id} returned /{endpoint_name} domain_id mismatch: expected "
            f"{expected_domain_id!r}, got {message.envelope.domain_id!r}"
        )
    if message.envelope.recipient_id != expected_recipient_id:
        raise ParticipantDiscoveryIdentityMismatchError(
            f"{expected_sender_id} returned /{endpoint_name} recipient_id mismatch: expected "
            f"{expected_recipient_id!r}, got {message.envelope.recipient_id!r}"
        )
    if message.payload.participant_id != expected_sender_id:
        raise ParticipantDiscoveryIdentityMismatchError(
            f"{expected_sender_id} returned /{endpoint_name} payload participant_id mismatch: "
            f"expected {expected_sender_id!r}, got {message.payload.participant_id!r}"
        )
    if message.payload.domain_id != expected_domain_id:
        raise ParticipantDiscoveryIdentityMismatchError(
            f"{expected_sender_id} returned /{endpoint_name} payload domain_id mismatch: "
            f"expected {expected_domain_id!r}, got {message.payload.domain_id!r}"
        )


def _derive_companion_endpoint_url(action_url: str, endpoint_name: str) -> str:
    """Replace the final path segment of a participant endpoint with a sibling endpoint."""
    split = urlsplit(action_url)
    segments = [segment for segment in split.path.split("/") if segment]
    if segments:
        segments[-1] = endpoint_name
    else:
        segments = [endpoint_name]
    companion_path = "/" + "/".join(segments)
    return urlunsplit((split.scheme, split.netloc, companion_path, "", ""))

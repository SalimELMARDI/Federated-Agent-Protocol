"""Typed registry and parse helpers for supported FAP messages."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Final, Mapping, TypeAlias, cast

from pydantic import BaseModel, ConfigDict, ValidationError

from fap_core.enums import MessageType, ProtocolVersion
from fap_core.messages.aggregate_result import AggregateResultMessage
from fap_core.messages.aggregate_submit import AggregateSubmitMessage
from fap_core.messages.exception import ExceptionMessage
from fap_core.messages.participant_profile import ParticipantProfileMessage
from fap_core.messages.participant_status import ParticipantStatusMessage
from fap_core.messages.policy_attest import PolicyAttestMessage
from fap_core.messages.task_accept import TaskAcceptMessage
from fap_core.messages.task_complete import TaskCompleteMessage
from fap_core.messages.task_create import TaskCreateMessage
from fap_core.messages.task_reject import TaskRejectMessage

SupportedMessage: TypeAlias = (
    AggregateResultMessage
    | AggregateSubmitMessage
    | ExceptionMessage
    | ParticipantProfileMessage
    | ParticipantStatusMessage
    | PolicyAttestMessage
    | TaskAcceptMessage
    | TaskCompleteMessage
    | TaskCreateMessage
    | TaskRejectMessage
)

MessageModel: TypeAlias = (
    type[AggregateResultMessage]
    | type[AggregateSubmitMessage]
    | type[ExceptionMessage]
    | type[ParticipantProfileMessage]
    | type[ParticipantStatusMessage]
    | type[PolicyAttestMessage]
    | type[TaskAcceptMessage]
    | type[TaskCompleteMessage]
    | type[TaskCreateMessage]
    | type[TaskRejectMessage]
)

SUPPORTED_PROTOCOL: Final[str] = "FAP"
SUPPORTED_VERSION: Final[ProtocolVersion] = ProtocolVersion.V0_1

MESSAGE_MODELS_BY_KIND: Final[Mapping[str, MessageModel]] = MappingProxyType(
    {
        MessageType.FAP_TASK_CREATE: TaskCreateMessage,
        MessageType.FAP_TASK_ACCEPT: TaskAcceptMessage,
        MessageType.FAP_TASK_REJECT: TaskRejectMessage,
        MessageType.FAP_TASK_COMPLETE: TaskCompleteMessage,
        MessageType.FAP_AGGREGATE_SUBMIT: AggregateSubmitMessage,
        MessageType.FAP_AGGREGATE_RESULT: AggregateResultMessage,
        MessageType.FAP_POLICY_ATTEST: PolicyAttestMessage,
        MessageType.FAP_PARTICIPANT_PROFILE: ParticipantProfileMessage,
        MessageType.FAP_PARTICIPANT_STATUS: ParticipantStatusMessage,
        MessageType.FAP_EXCEPTION: ExceptionMessage,
    }
)

MESSAGE_MODELS_BY_DISPATCH_KEY: Final[Mapping[tuple[str, str, str], MessageModel]] = MappingProxyType(
    {
        (SUPPORTED_PROTOCOL, SUPPORTED_VERSION.value, kind): model
        for kind, model in MESSAGE_MODELS_BY_KIND.items()
    }
)


class MessageParseError(Exception):
    """Raised when raw data cannot be parsed into a supported FAP message."""


class UnknownMessageKindError(MessageParseError):
    """Raised when a message kind is not present in the registry."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        super().__init__(f"Unsupported message kind: {kind!r}")


class UnsupportedProtocolVersionError(MessageParseError):
    """Raised when a message declares an unsupported FAP protocol version."""

    def __init__(self, *, protocol: str, version: str) -> None:
        self.protocol = protocol
        self.version = version
        super().__init__(f"Unsupported protocol version for {protocol!r}: {version!r}")


class _EnvelopeKindProbe(BaseModel):
    """Minimal envelope view used to determine dispatch target."""

    model_config = ConfigDict(extra="allow")

    protocol: str
    version: str
    message_type: str


class _MessageKindProbe(BaseModel):
    """Minimal top-level model used to extract the message kind."""

    model_config = ConfigDict(extra="allow")

    envelope: _EnvelopeKindProbe


def get_message_model(
    kind: str,
    *,
    protocol: str = SUPPORTED_PROTOCOL,
    version: str | ProtocolVersion = SUPPORTED_VERSION,
) -> MessageModel:
    """Return the registered message model for a supported FAP dispatch key."""
    normalized_version = version.value if isinstance(version, ProtocolVersion) else version
    if protocol != SUPPORTED_PROTOCOL:
        raise MessageParseError(f"Unsupported protocol: {protocol!r}")
    if normalized_version != SUPPORTED_VERSION.value:
        raise UnsupportedProtocolVersionError(protocol=protocol, version=normalized_version)

    try:
        return MESSAGE_MODELS_BY_DISPATCH_KEY[(protocol, normalized_version, kind)]
    except KeyError as exc:
        raise UnknownMessageKindError(kind) from exc


def parse_message(data: dict[str, Any]) -> SupportedMessage:
    """Parse raw message data into the correct typed FAP message model."""
    try:
        envelope = _MessageKindProbe.model_validate(data).envelope
    except ValidationError as exc:
        raise MessageParseError(
            "Malformed message envelope: expected protocol, version, and message_type strings."
        ) from exc

    model = get_message_model(
        envelope.message_type,
        protocol=envelope.protocol,
        version=envelope.version,
    )

    try:
        return cast(SupportedMessage, model.model_validate(data))
    except ValidationError as exc:
        raise MessageParseError(f"Failed to parse message kind {envelope.message_type!r}.") from exc

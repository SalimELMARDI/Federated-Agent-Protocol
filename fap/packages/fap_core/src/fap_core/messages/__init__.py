"""Shared message models for the Federated Agent Protocol."""

from fap_core.messages.aggregate_result import AggregateResultMessage, AggregateResultPayload
from fap_core.messages.aggregate_submit import AggregateSubmitMessage, AggregateSubmitPayload
from fap_core.messages.envelope import GovernanceMetadata, MessageEnvelope
from fap_core.messages.exception import ExceptionMessage, ExceptionPayload
from fap_core.messages.policy_attest import PolicyAttestMessage, PolicyAttestPayload
from fap_core.messages.registry import (
    MESSAGE_MODELS_BY_DISPATCH_KEY,
    MESSAGE_MODELS_BY_KIND,
    MessageModel,
    MessageParseError,
    SupportedMessage,
    SUPPORTED_PROTOCOL,
    SUPPORTED_VERSION,
    UnsupportedProtocolVersionError,
    UnknownMessageKindError,
    get_message_model,
    parse_message,
)
from fap_core.messages.source_refs import SourceRef
from fap_core.messages.task_accept import TaskAcceptMessage, TaskAcceptPayload
from fap_core.messages.task_complete import TaskCompleteMessage, TaskCompletePayload
from fap_core.messages.task_create import TaskCreateMessage, TaskCreatePayload
from fap_core.messages.task_reject import TaskRejectMessage, TaskRejectPayload

__all__ = [
    "AggregateResultMessage",
    "AggregateResultPayload",
    "AggregateSubmitMessage",
    "AggregateSubmitPayload",
    "ExceptionMessage",
    "ExceptionPayload",
    "MESSAGE_MODELS_BY_DISPATCH_KEY",
    "GovernanceMetadata",
    "MESSAGE_MODELS_BY_KIND",
    "MessageEnvelope",
    "MessageModel",
    "MessageParseError",
    "PolicyAttestMessage",
    "PolicyAttestPayload",
    "SupportedMessage",
    "SUPPORTED_PROTOCOL",
    "SUPPORTED_VERSION",
    "SourceRef",
    "TaskAcceptMessage",
    "TaskAcceptPayload",
    "TaskCompleteMessage",
    "TaskCompletePayload",
    "TaskCreateMessage",
    "TaskCreatePayload",
    "TaskRejectMessage",
    "TaskRejectPayload",
    "UnsupportedProtocolVersionError",
    "UnknownMessageKindError",
    "get_message_model",
    "parse_message",
]

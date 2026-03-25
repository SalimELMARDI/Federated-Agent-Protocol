"""Coordinator dispatch helpers for participant_docs evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping, cast

import httpx

from coordinator_api.service.persistence import PersistenceError
from coordinator_api.service.store import CoordinatorStore
from fap_core import message_from_dict, message_to_dict
from fap_core.identity import (
    ParticipantId,
    TrustedParticipantIdentity,
    get_trusted_participant_identity,
)
from fap_core.messages import (
    AggregateSubmitMessage,
    MessageParseError,
    PolicyAttestMessage,
    TaskAcceptMessage,
    TaskCompleteMessage,
    TaskRejectMessage,
    UnknownMessageKindError,
)


class RunNotFoundError(Exception):
    """Raised when a dispatch targets an unknown run."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"Run not found: {run_id!r}")


class ParticipantEvaluationFailedError(Exception):
    """Raised when downstream participant evaluation fails at the transport layer."""


class InvalidParticipantResponseError(Exception):
    """Raised when a participant returns an invalid or unsupported FAP response."""


class ParticipantExecutionFailedError(Exception):
    """Raised when downstream participant execution fails at the transport layer."""


class InvalidParticipantExecutionResponseError(Exception):
    """Raised when a participant returns an invalid execution response payload."""


class ParticipantIdentityMismatchError(Exception):
    """Raised when a participant response does not match the trusted identity."""


@dataclass(frozen=True)
class TrustedParticipantConfig:
    """Coordinator-side trusted participant endpoint configuration."""

    identity: TrustedParticipantIdentity
    evaluate_url: str
    execute_url: str
    transport: httpx.AsyncBaseTransport | None = None


TrustedParticipantRegistry = Mapping[ParticipantId, TrustedParticipantConfig]


@dataclass(frozen=True)
class ParticipantExecutionDispatchResult:
    """Canonical result bundle returned by participant_docs execution dispatch."""

    task_complete_message: TaskCompleteMessage
    policy_attest_message: PolicyAttestMessage
    aggregate_submit_message: AggregateSubmitMessage


def build_trusted_participant_config(
    participant_id: ParticipantId | str,
    *,
    evaluate_url: str,
    execute_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> TrustedParticipantConfig:
    """Build a typed trusted participant configuration for coordinator runtime use."""
    return TrustedParticipantConfig(
        identity=get_trusted_participant_identity(participant_id),
        evaluate_url=evaluate_url,
        execute_url=execute_url,
        transport=transport,
    )


def build_trusted_participant_registry(
    *,
    participant_docs_evaluate_url: str,
    participant_docs_execute_url: str,
    participant_docs_transport: httpx.AsyncBaseTransport | None = None,
    participant_kb_evaluate_url: str,
    participant_kb_execute_url: str,
    participant_kb_transport: httpx.AsyncBaseTransport | None = None,
    participant_logs_evaluate_url: str,
    participant_logs_execute_url: str,
    participant_logs_transport: httpx.AsyncBaseTransport | None = None,
) -> TrustedParticipantRegistry:
    """Build the coordinator's central trusted participant registry."""
    return MappingProxyType(
        {
            ParticipantId.PARTICIPANT_DOCS: build_trusted_participant_config(
                ParticipantId.PARTICIPANT_DOCS,
                evaluate_url=participant_docs_evaluate_url,
                execute_url=participant_docs_execute_url,
                transport=participant_docs_transport,
            ),
            ParticipantId.PARTICIPANT_KB: build_trusted_participant_config(
                ParticipantId.PARTICIPANT_KB,
                evaluate_url=participant_kb_evaluate_url,
                execute_url=participant_kb_execute_url,
                transport=participant_kb_transport,
            ),
            ParticipantId.PARTICIPANT_LOGS: build_trusted_participant_config(
                ParticipantId.PARTICIPANT_LOGS,
                evaluate_url=participant_logs_evaluate_url,
                execute_url=participant_logs_execute_url,
                transport=participant_logs_transport,
            ),
        }
    )


async def dispatch_run_to_participant_docs(
    run_id: str,
    *,
    store: CoordinatorStore,
    evaluate_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> TaskAcceptMessage | TaskRejectMessage:
    """Dispatch a stored task-create run to participant_docs and record the returned decision."""
    return await _dispatch_run_to_participant(
        run_id,
        store=store,
        url=evaluate_url,
        transport=transport,
        participant_id=ParticipantId.PARTICIPANT_DOCS,
    )


async def dispatch_run_to_participant_kb(
    run_id: str,
    *,
    store: CoordinatorStore,
    evaluate_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> TaskAcceptMessage | TaskRejectMessage:
    """Dispatch a stored task-create run to participant_kb and record the returned decision."""
    return await _dispatch_run_to_participant(
        run_id,
        store=store,
        url=evaluate_url,
        transport=transport,
        participant_id=ParticipantId.PARTICIPANT_KB,
    )


async def dispatch_run_to_participant_logs(
    run_id: str,
    *,
    store: CoordinatorStore,
    evaluate_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> TaskAcceptMessage | TaskRejectMessage:
    """Dispatch a stored task-create run to participant_logs and record the returned decision."""
    return await _dispatch_run_to_participant(
        run_id,
        store=store,
        url=evaluate_url,
        transport=transport,
        participant_id=ParticipantId.PARTICIPANT_LOGS,
    )


async def _dispatch_run_to_participant(
    run_id: str,
    *,
    store: CoordinatorStore,
    url: str,
    transport: httpx.AsyncBaseTransport | None = None,
    participant_id: ParticipantId,
) -> TaskAcceptMessage | TaskRejectMessage:
    """Dispatch a stored task-create run to a participant evaluation endpoint."""
    participant_identity = get_trusted_participant_identity(participant_id)
    participant_name = participant_identity.participant_id.value
    if store.get_run(run_id) is None:
        raise RunNotFoundError(run_id)

    task_create_message = store.get_task_create_message(run_id)
    if task_create_message is None:
        raise PersistenceError(f"Persisted task-create message not found for run: {run_id!r}")

    try:
        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.post(url, json=message_to_dict(task_create_message))
    except httpx.HTTPError as exc:
        raise ParticipantEvaluationFailedError(
            f"{participant_name} evaluation request failed: {exc}"
        ) from exc

    if response.status_code != 200:
        raise ParticipantEvaluationFailedError(
            f"{participant_name} evaluation failed with status {response.status_code}"
        )

    try:
        raw = response.json()
    except ValueError as exc:
        raise InvalidParticipantResponseError(f"{participant_name} returned invalid JSON response") from exc

    if not isinstance(raw, dict):
        raise InvalidParticipantResponseError(f"{participant_name} returned non-object JSON response")

    try:
        parsed = message_from_dict(cast(dict[str, object], raw))
    except (MessageParseError, UnknownMessageKindError) as exc:
        raise InvalidParticipantResponseError(str(exc)) from exc

    if isinstance(parsed, TaskAcceptMessage | TaskRejectMessage):
        _validate_message_identity(
            parsed,
            participant_identity=participant_identity,
            expected_recipient_id=task_create_message.envelope.sender_id,
            response_label="evaluation response",
        )
        store.record_message(parsed)
        return parsed

    raise InvalidParticipantResponseError(
        f"{participant_name} returned unsupported decision message type: "
        f"{parsed.envelope.message_type.value!r}"
    )


async def dispatch_run_to_participant_docs_execute(
    run_id: str,
    *,
    store: CoordinatorStore,
    execute_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ParticipantExecutionDispatchResult:
    """Dispatch a stored task-create run to participant_docs execution and record the outputs."""
    return await _dispatch_run_to_participant_execute(
        run_id,
        store=store,
        url=execute_url,
        transport=transport,
        participant_id=ParticipantId.PARTICIPANT_DOCS,
    )


async def dispatch_run_to_participant_kb_execute(
    run_id: str,
    *,
    store: CoordinatorStore,
    execute_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ParticipantExecutionDispatchResult:
    """Dispatch a stored task-create run to participant_kb execution and record the outputs."""
    return await _dispatch_run_to_participant_execute(
        run_id,
        store=store,
        url=execute_url,
        transport=transport,
        participant_id=ParticipantId.PARTICIPANT_KB,
    )


async def dispatch_run_to_participant_logs_execute(
    run_id: str,
    *,
    store: CoordinatorStore,
    execute_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ParticipantExecutionDispatchResult:
    """Dispatch a stored task-create run to participant_logs execution and record the outputs."""
    return await _dispatch_run_to_participant_execute(
        run_id,
        store=store,
        url=execute_url,
        transport=transport,
        participant_id=ParticipantId.PARTICIPANT_LOGS,
    )


async def _dispatch_run_to_participant_execute(
    run_id: str,
    *,
    store: CoordinatorStore,
    url: str,
    transport: httpx.AsyncBaseTransport | None = None,
    participant_id: ParticipantId,
) -> ParticipantExecutionDispatchResult:
    """Dispatch a stored task-create run to a participant execution endpoint."""
    participant_identity = get_trusted_participant_identity(participant_id)
    participant_name = participant_identity.participant_id.value
    if store.get_run(run_id) is None:
        raise RunNotFoundError(run_id)

    task_create_message = store.get_task_create_message(run_id)
    if task_create_message is None:
        raise PersistenceError(f"Persisted task-create message not found for run: {run_id!r}")

    try:
        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.post(url, json=message_to_dict(task_create_message))
    except httpx.HTTPError as exc:
        raise ParticipantExecutionFailedError(
            f"{participant_name} execution request failed: {exc}"
        ) from exc

    if response.status_code != 200:
        raise ParticipantExecutionFailedError(
            f"{participant_name} execution failed with status {response.status_code}"
        )

    try:
        raw = response.json()
    except ValueError as exc:
        raise InvalidParticipantExecutionResponseError(
            f"{participant_name} returned invalid JSON response"
        ) from exc

    if not isinstance(raw, dict):
        raise InvalidParticipantExecutionResponseError(
            f"{participant_name} returned non-object JSON response"
        )

    task_complete_raw = _extract_execution_message(
        raw, field_name="task_complete", participant_name=participant_name
    )
    policy_attest_raw = _extract_execution_message(
        raw, field_name="policy_attest", participant_name=participant_name
    )
    aggregate_submit_raw = _extract_execution_message(
        raw, field_name="aggregate_submit", participant_name=participant_name
    )
    task_complete = _parse_execution_message(task_complete_raw)
    policy_attest = _parse_execution_message(policy_attest_raw)
    aggregate_submit = _parse_execution_message(aggregate_submit_raw)

    if not isinstance(task_complete, TaskCompleteMessage) or not isinstance(
        policy_attest, PolicyAttestMessage
    ) or not isinstance(aggregate_submit, AggregateSubmitMessage):
        raise InvalidParticipantExecutionResponseError(
            f"{participant_name} returned unexpected execution message types"
        )

    expected_recipient_id = task_create_message.envelope.sender_id
    _validate_message_identity(
        task_complete,
        participant_identity=participant_identity,
        expected_recipient_id=expected_recipient_id,
        response_label="task_complete",
    )
    _validate_message_identity(
        policy_attest,
        participant_identity=participant_identity,
        expected_recipient_id=expected_recipient_id,
        response_label="policy_attest",
    )
    _validate_message_identity(
        aggregate_submit,
        participant_identity=participant_identity,
        expected_recipient_id=expected_recipient_id,
        response_label="aggregate_submit",
    )
    if aggregate_submit.payload.participant_id != task_complete.payload.participant_id:
        raise InvalidParticipantExecutionResponseError(
            f"{participant_name} returned mismatched aggregate submission participant id"
        )
    _validate_payload_participant_id(
        task_complete,
        participant_identity=participant_identity,
        response_label="task_complete",
    )
    _validate_payload_participant_id(
        policy_attest,
        participant_identity=participant_identity,
        response_label="policy_attest",
    )
    _validate_payload_participant_id(
        aggregate_submit,
        participant_identity=participant_identity,
        response_label="aggregate_submit",
    )

    store.record_task_complete(task_complete)
    store.record_policy_attest(policy_attest)
    store.record_aggregate_submit(aggregate_submit)
    return ParticipantExecutionDispatchResult(
        task_complete_message=task_complete,
        policy_attest_message=policy_attest,
        aggregate_submit_message=aggregate_submit,
    )


def _extract_execution_message(
    data: dict[str, object], *, field_name: str, participant_name: str
) -> dict[str, object]:
    """Return a required top-level execution message field as canonical FAP data."""
    if field_name not in data:
        raise InvalidParticipantExecutionResponseError(
            f"{participant_name} execution response is missing {field_name!r}"
        )

    raw_message = data[field_name]
    if not isinstance(raw_message, dict):
        raise InvalidParticipantExecutionResponseError(
            f"{participant_name} execution field {field_name!r} must be an object"
        )

    return cast(dict[str, object], raw_message)


def _parse_execution_message(data: dict[str, object]) -> object:
    """Parse a nested execution message field through the shared FAP parser."""
    try:
        return message_from_dict(data)
    except (MessageParseError, UnknownMessageKindError) as exc:
        raise InvalidParticipantExecutionResponseError(str(exc)) from exc


def _validate_message_identity(
    message: TaskAcceptMessage | TaskRejectMessage | TaskCompleteMessage | PolicyAttestMessage | AggregateSubmitMessage,
    *,
    participant_identity: TrustedParticipantIdentity,
    expected_recipient_id: str,
    response_label: str,
) -> None:
    """Ensure the returned message envelope matches the trusted participant identity."""
    expected_sender_id = participant_identity.participant_id.value
    expected_domain_id = participant_identity.domain_id
    actual_sender_id = message.envelope.sender_id
    actual_domain_id = message.envelope.domain_id
    actual_recipient_id = message.envelope.recipient_id

    if (
        actual_sender_id == expected_sender_id
        and actual_domain_id == expected_domain_id
        and actual_recipient_id == expected_recipient_id
    ):
        return

    raise ParticipantIdentityMismatchError(
        f"{expected_sender_id} returned {response_label} identity mismatch: expected "
        f"sender_id/domain_id/recipient_id {expected_sender_id!r}/{expected_domain_id!r}/"
        f"{expected_recipient_id!r}, got {actual_sender_id!r}/{actual_domain_id!r}/"
        f"{actual_recipient_id!r}"
    )


def _validate_payload_participant_id(
    message: TaskAcceptMessage | TaskRejectMessage | TaskCompleteMessage | PolicyAttestMessage | AggregateSubmitMessage,
    *,
    participant_identity: TrustedParticipantIdentity,
    response_label: str,
) -> None:
    """Ensure the payload participant id matches the trusted participant identity."""
    expected_participant_id = participant_identity.participant_id.value
    actual_participant_id = message.payload.participant_id
    if actual_participant_id == expected_participant_id:
        return

    raise ParticipantIdentityMismatchError(
        f"{expected_participant_id} returned {response_label} payload participant_id mismatch: "
        f"expected {expected_participant_id!r}, got {actual_participant_id!r}"
    )


__all__: Final[list[str]] = [
    "InvalidParticipantExecutionResponseError",
    "InvalidParticipantResponseError",
    "ParticipantEvaluationFailedError",
    "ParticipantExecutionDispatchResult",
    "ParticipantExecutionFailedError",
    "ParticipantIdentityMismatchError",
    "RunNotFoundError",
    "TrustedParticipantConfig",
    "TrustedParticipantRegistry",
    "build_trusted_participant_config",
    "build_trusted_participant_registry",
    "dispatch_run_to_participant_docs",
    "dispatch_run_to_participant_docs_execute",
    "dispatch_run_to_participant_kb",
    "dispatch_run_to_participant_kb_execute",
    "dispatch_run_to_participant_logs",
    "dispatch_run_to_participant_logs_execute",
]

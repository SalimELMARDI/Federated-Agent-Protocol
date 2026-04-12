"""FAP protocol compliance tests for participant_llm.

Validates that participant_llm conforms to every protocol-level invariant
required by the FAP v0.1 specification:

- Participant is registered in the trusted identity table
- All output envelopes carry the canonical participant routing fields
- FAP message-type string values match the specification literals
- The three-message execution bundle is self-consistent
- source_refs follow the required schema
- Policy attestation is linked to aggregate_submit via provenance_ref
"""

from __future__ import annotations

import pytest
from pytest import MonkeyPatch

from fap_core.clocks import utc_now
from fap_core.enums import AggregateContributionType, MessageType
from fap_core.identity import TRUSTED_PARTICIPANT_IDENTITIES, ParticipantId
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import MessageEnvelope, TaskCreateMessage, TaskCreatePayload
from participant_llm.adapters.llm_client import LLMResponse
from participant_llm.service.evaluator import evaluate_task_create
from participant_llm.service.executor import execute_task_create

STUB_MODEL = "compliance-stub-v1"
STUB_ENDPOINT = "https://compliance.example.com/v1"
STUB_CONTENT = "Compliance stub response."


async def _stub_llm(query: str) -> LLMResponse:
    del query
    return LLMResponse(content=STUB_CONTENT, model=STUB_MODEL, endpoint_url=STUB_ENDPOINT)


def _build_message() -> TaskCreateMessage:
    return TaskCreateMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_CREATE,
            task_id=new_task_id(),
            run_id=new_run_id(),
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id="participant_llm",
            domain_id="participant_llm",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
        ),
        payload=TaskCreatePayload(
            title="Compliance probe",
            description="FAP protocol compliance probe.",
            requested_capabilities=["llm.query"],
            input_query="compliance check",
        ),
    )


# ---------------------------------------------------------------------------
# Identity registration
# ---------------------------------------------------------------------------


def test_participant_llm_is_registered_in_trusted_identity_table() -> None:
    """participant_llm must appear in fap_core's TRUSTED_PARTICIPANT_IDENTITIES."""
    assert ParticipantId.PARTICIPANT_LLM in TRUSTED_PARTICIPANT_IDENTITIES


def test_participant_llm_trusted_identity_has_correct_ids() -> None:
    """The trusted identity entry must use 'participant_llm' for both participant and domain."""
    identity = TRUSTED_PARTICIPANT_IDENTITIES[ParticipantId.PARTICIPANT_LLM]
    assert identity.participant_id == "participant_llm"
    assert identity.domain_id == "participant_llm"


# ---------------------------------------------------------------------------
# Message-type string literals (FAP spec §2)
# ---------------------------------------------------------------------------


def test_task_accept_message_type_string() -> None:
    """fap.task.accept message type must match the FAP spec literal."""
    inbound = _build_message()
    decision = evaluate_task_create(inbound)
    assert decision.envelope.message_type.value == "fap.task.accept"


@pytest.mark.asyncio
async def test_task_complete_message_type_string(monkeypatch: MonkeyPatch) -> None:
    """fap.task.complete message type must match the FAP spec literal."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    result = await execute_task_create(_build_message())
    assert result.task_complete_message.envelope.message_type.value == "fap.task.complete"


@pytest.mark.asyncio
async def test_policy_attest_message_type_string(monkeypatch: MonkeyPatch) -> None:
    """fap.policy.attest message type must match the FAP spec literal."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    result = await execute_task_create(_build_message())
    assert result.policy_attest_message.envelope.message_type.value == "fap.policy.attest"


@pytest.mark.asyncio
async def test_aggregate_submit_message_type_string(monkeypatch: MonkeyPatch) -> None:
    """fap.aggregate.submit message type must match the FAP spec literal."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    result = await execute_task_create(_build_message())
    assert result.aggregate_submit_message.envelope.message_type.value == "fap.aggregate.submit"


# ---------------------------------------------------------------------------
# Envelope routing (FAP spec §3 — participant routing fields)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_output_envelopes_have_sender_id_participant_llm(
    monkeypatch: MonkeyPatch,
) -> None:
    """All three output envelopes must identify participant_llm as the sender."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    result = await execute_task_create(_build_message())

    for msg in (
        result.task_complete_message,
        result.policy_attest_message,
        result.aggregate_submit_message,
    ):
        assert msg.envelope.sender_id == "participant_llm", (
            f"{msg.envelope.message_type.value} sender_id mismatch"
        )


@pytest.mark.asyncio
async def test_all_output_envelopes_have_domain_id_participant_llm(
    monkeypatch: MonkeyPatch,
) -> None:
    """All three output envelopes must set domain_id to 'participant_llm'."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    result = await execute_task_create(_build_message())

    for msg in (
        result.task_complete_message,
        result.policy_attest_message,
        result.aggregate_submit_message,
    ):
        assert msg.envelope.domain_id == "participant_llm", (
            f"{msg.envelope.message_type.value} domain_id mismatch"
        )


@pytest.mark.asyncio
async def test_all_output_envelopes_route_back_to_inbound_sender(
    monkeypatch: MonkeyPatch,
) -> None:
    """All three output envelopes must address the inbound message's sender as recipient."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    inbound = _build_message()
    result = await execute_task_create(inbound)

    for msg in (
        result.task_complete_message,
        result.policy_attest_message,
        result.aggregate_submit_message,
    ):
        assert msg.envelope.recipient_id == inbound.envelope.sender_id, (
            f"{msg.envelope.message_type.value} recipient_id mismatch"
        )


@pytest.mark.asyncio
async def test_all_output_envelopes_mirror_task_run_trace_ids(
    monkeypatch: MonkeyPatch,
) -> None:
    """All three output envelopes must carry the exact task_id, run_id, trace_id from inbound."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    inbound = _build_message()
    result = await execute_task_create(inbound)

    for msg in (
        result.task_complete_message,
        result.policy_attest_message,
        result.aggregate_submit_message,
    ):
        assert msg.envelope.task_id == inbound.envelope.task_id
        assert msg.envelope.run_id == inbound.envelope.run_id
        assert msg.envelope.trace_id == inbound.envelope.trace_id


# ---------------------------------------------------------------------------
# source_refs schema (FAP spec §5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_source_ref_participant_id_is_participant_llm(monkeypatch: MonkeyPatch) -> None:
    """source_ref.participant_id must be 'participant_llm'."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    result = await execute_task_create(_build_message())

    assert result.task_complete_message.payload.source_refs[0].participant_id == "participant_llm"


@pytest.mark.asyncio
async def test_source_ref_source_id_is_model_name(monkeypatch: MonkeyPatch) -> None:
    """source_ref.source_id must be the model name (machine-readable identifier)."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    result = await execute_task_create(_build_message())

    assert result.task_complete_message.payload.source_refs[0].source_id == STUB_MODEL


@pytest.mark.asyncio
async def test_source_ref_source_path_is_endpoint_url(monkeypatch: MonkeyPatch) -> None:
    """source_ref.source_path must be the API endpoint URL."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    result = await execute_task_create(_build_message())

    assert result.task_complete_message.payload.source_refs[0].source_path == STUB_ENDPOINT


# ---------------------------------------------------------------------------
# Aggregate submit payload (FAP spec §6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregate_submit_contribution_type_is_summary(monkeypatch: MonkeyPatch) -> None:
    """aggregate_submit contribution_type must be SUMMARY for a standard LLM response."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    result = await execute_task_create(_build_message())

    assert (
        result.aggregate_submit_message.payload.contribution_type
        == AggregateContributionType.SUMMARY
    )


@pytest.mark.asyncio
async def test_aggregate_submit_participant_id_is_participant_llm(monkeypatch: MonkeyPatch) -> None:
    """aggregate_submit.participant_id must identify this participant."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    result = await execute_task_create(_build_message())

    assert result.aggregate_submit_message.payload.participant_id == "participant_llm"


@pytest.mark.asyncio
async def test_aggregate_submit_provenance_ref_equals_policy_attest_message_id(
    monkeypatch: MonkeyPatch,
) -> None:
    """aggregate_submit.provenance_ref must point to policy_attest.envelope.message_id."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    result = await execute_task_create(_build_message())

    assert (
        result.aggregate_submit_message.payload.provenance_ref
        == result.policy_attest_message.envelope.message_id
    )


@pytest.mark.asyncio
async def test_aggregate_submit_summary_equals_task_complete_summary(
    monkeypatch: MonkeyPatch,
) -> None:
    """aggregate_submit.summary must be identical to task_complete.summary."""
    monkeypatch.setattr("participant_llm.service.executor.call_llm", _stub_llm)
    result = await execute_task_create(_build_message())

    assert (
        result.aggregate_submit_message.payload.summary
        == result.task_complete_message.payload.summary
    )

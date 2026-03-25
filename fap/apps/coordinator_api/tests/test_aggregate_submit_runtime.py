"""Tests for coordinator runtime aggregate-submit activation."""

from __future__ import annotations

from coordinator_api.service.store import InMemoryRunStore
from fap_core.clocks import utc_now
from fap_core.enums import (
    AggregateContributionType,
    MessageType,
    PolicyTransformType,
    PrivacyClass,
    SharingMode,
    TaskCompleteStatus,
)
from fap_core.ids import new_message_id, new_run_id, new_task_id, new_trace_id
from fap_core.messages import (
    AggregateSubmitMessage,
    AggregateSubmitPayload,
    MessageEnvelope,
    PolicyAttestMessage,
    PolicyAttestPayload,
    SourceRef,
    TaskCompleteMessage,
    TaskCompletePayload,
    TaskCreateMessage,
    TaskCreatePayload,
)


def build_create_message() -> TaskCreateMessage:
    """Return a valid task-create message for aggregate-submit runtime tests."""
    return TaskCreateMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_CREATE,
            task_id=new_task_id(),
            run_id=new_run_id(),
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id="participant_docs",
            domain_id="docs",
            trace_id=new_trace_id(),
            timestamp=utc_now(),
        ),
        payload=TaskCreatePayload(
            title="Aggregate participant execution",
            description="Build a canonical aggregation input.",
            requested_capabilities=["docs.search"],
            input_query="privacy",
        ),
    )


def build_task_complete(create_message: TaskCreateMessage) -> TaskCompleteMessage:
    """Return a valid task-complete message derived from a task-create run."""
    return TaskCompleteMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_COMPLETE,
            task_id=create_message.envelope.task_id,
            run_id=create_message.envelope.run_id,
            message_id=new_message_id(),
            sender_id="participant_docs",
            recipient_id="coordinator",
            domain_id="participant_docs",
            trace_id=create_message.envelope.trace_id,
            timestamp=utc_now(),
        ),
        payload=TaskCompletePayload(
            participant_id="participant_docs",
            status=TaskCompleteStatus.COMPLETED,
            summary="[SUMMARY ONLY] Matched docs: Privacy Policy Memo",
            source_refs=[
                SourceRef(
                    participant_id="participant_docs",
                    source_id="doc-002",
                    source_title="Privacy Policy Memo",
                    source_path="examples/local_docs/data/doc-002__privacy-policy-memo.json",
                )
            ],
        ),
    )


def build_policy_attest(
    create_message: TaskCreateMessage, *, message_id: str | None = None
) -> PolicyAttestMessage:
    """Return a valid policy-attest message derived from a task-create run."""
    return PolicyAttestMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_POLICY_ATTEST,
            task_id=create_message.envelope.task_id,
            run_id=create_message.envelope.run_id,
            message_id=new_message_id() if message_id is None else message_id,
            sender_id="participant_docs",
            recipient_id="coordinator",
            domain_id="participant_docs",
            trace_id=create_message.envelope.trace_id,
            timestamp=utc_now(),
        ),
        payload=PolicyAttestPayload(
            participant_id="participant_docs",
            policy_ref="policy.docs.v0",
            original_privacy_class=PrivacyClass.INTERNAL,
            applied_sharing_mode=SharingMode.SUMMARY_ONLY,
            transform_type=PolicyTransformType.SUMMARY_ONLY,
        ),
    )


def build_aggregate_submit(
    create_message: TaskCreateMessage,
    *,
    provenance_ref: str,
) -> AggregateSubmitMessage:
    """Return a participant-originated aggregate-submit message for a run."""
    return AggregateSubmitMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_AGGREGATE_SUBMIT,
            task_id=create_message.envelope.task_id,
            run_id=create_message.envelope.run_id,
            message_id=new_message_id(),
            sender_id="participant_docs",
            recipient_id="coordinator",
            domain_id="participant_docs",
            trace_id=create_message.envelope.trace_id,
            timestamp=utc_now(),
        ),
        payload=AggregateSubmitPayload(
            participant_id="participant_docs",
            contribution_type=AggregateContributionType.SUMMARY,
            summary="[SUMMARY ONLY] Matched docs: Privacy Policy Memo",
            provenance_ref=provenance_ref,
            source_refs=[
                SourceRef(
                    participant_id="participant_docs",
                    source_id="doc-002",
                    source_title="Privacy Policy Memo",
                    source_path="examples/local_docs/data/doc-002__privacy-policy-memo.json",
                )
            ],
        ),
    )


def test_build_aggregate_submit_from_execution_uses_completed_summary() -> None:
    """Participant-originated aggregate submissions should carry the governed summary."""
    create_message = build_create_message()
    policy_attest = build_policy_attest(create_message)

    aggregate_submit = build_aggregate_submit(
        create_message,
        provenance_ref=policy_attest.envelope.message_id,
    )

    assert aggregate_submit.envelope.message_type == MessageType.FAP_AGGREGATE_SUBMIT
    assert aggregate_submit.payload.participant_id == "participant_docs"
    assert aggregate_submit.payload.contribution_type == AggregateContributionType.SUMMARY
    assert (
        aggregate_submit.payload.summary
        == "[SUMMARY ONLY] Matched docs: Privacy Policy Memo"
    )
    assert aggregate_submit.payload.vote is None
    assert aggregate_submit.payload.source_refs[0].source_id == "doc-002"


def test_provenance_ref_comes_from_matching_policy_attestation_message_id() -> None:
    """Aggregate submissions should point back to the participant policy attestation."""
    create_message = build_create_message()
    policy_attest_id = new_message_id()
    aggregate_submit = build_aggregate_submit(
        create_message,
        provenance_ref=policy_attest_id,
    )

    assert aggregate_submit.payload.provenance_ref == policy_attest_id


def test_recorded_aggregate_submit_updates_run_snapshot_state() -> None:
    """Recording an aggregate submission should update the tracked run projection."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    policy_attest = build_policy_attest(create_message)
    aggregate_submit = build_aggregate_submit(
        create_message,
        provenance_ref=policy_attest.envelope.message_id,
    )
    store.record_task_create(create_message)

    snapshot = store.record_aggregate_submit(aggregate_submit)

    assert snapshot.aggregate_submissions[0].participant_id == "participant_docs"
    assert snapshot.aggregate_submissions[0].contribution_type == AggregateContributionType.SUMMARY
    assert snapshot.aggregate_submissions[0].summary == aggregate_submit.payload.summary
    assert snapshot.aggregate_submissions[0].source_refs[0].source_id == "doc-002"
    assert snapshot.last_message_type == "fap.aggregate.submit"
    assert snapshot.message_count == 2


def test_aggregate_submit_preserves_task_run_and_trace_ids() -> None:
    """Aggregate submissions should preserve the originating run context."""
    create_message = build_create_message()
    aggregate_submit = build_aggregate_submit(
        create_message,
        provenance_ref=new_message_id(),
    )

    assert aggregate_submit.envelope.task_id == create_message.envelope.task_id
    assert aggregate_submit.envelope.run_id == create_message.envelope.run_id
    assert aggregate_submit.envelope.trace_id == create_message.envelope.trace_id

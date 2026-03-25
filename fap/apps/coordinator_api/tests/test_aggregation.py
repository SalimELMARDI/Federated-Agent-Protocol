"""Tests for coordinator aggregation helpers."""

from __future__ import annotations

import pytest

from coordinator_api.service.aggregation import (
    NoCompletedParticipantsError,
    aggregate_run_summary_merge,
)
from coordinator_api.service.store import InMemoryRunStore
from fap_core.clocks import utc_now
from fap_core.enums import (
    AggregateContributionType,
    AggregationMode,
    MessageType,
    PolicyTransformType,
    PrivacyClass,
    RunStatus,
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
    """Return a valid task-create message for aggregation tests."""
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
            title="Aggregate governed outputs",
            description="Merge deterministic participant summaries.",
            requested_capabilities=["docs.search"],
            input_query="privacy",
        ),
    )


def build_task_complete(
    create_message: TaskCreateMessage, *, participant_id: str, summary: str, source_refs: list[SourceRef] | None = None
) -> TaskCompleteMessage:
    """Return a valid task-complete message derived from a task-create run."""
    return TaskCompleteMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_TASK_COMPLETE,
            task_id=create_message.envelope.task_id,
            run_id=create_message.envelope.run_id,
            message_id=new_message_id(),
            sender_id=participant_id,
            recipient_id="coordinator",
            domain_id=participant_id,
            trace_id=create_message.envelope.trace_id,
            timestamp=utc_now(),
        ),
        payload=TaskCompletePayload(
            participant_id=participant_id,
            status=TaskCompleteStatus.COMPLETED,
            summary=summary,
            source_refs=[] if source_refs is None else source_refs,
        ),
    )


def build_policy_attest(
    create_message: TaskCreateMessage,
    *,
    participant_id: str,
    policy_ref: str,
    message_id: str | None = None,
) -> PolicyAttestMessage:
    """Return a valid policy-attest message derived from a task-create run."""
    return PolicyAttestMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_POLICY_ATTEST,
            task_id=create_message.envelope.task_id,
            run_id=create_message.envelope.run_id,
            message_id=new_message_id() if message_id is None else message_id,
            sender_id=participant_id,
            recipient_id="coordinator",
            domain_id=participant_id,
            trace_id=create_message.envelope.trace_id,
            timestamp=utc_now(),
        ),
        payload=PolicyAttestPayload(
            participant_id=participant_id,
            policy_ref=policy_ref,
            original_privacy_class=PrivacyClass.INTERNAL,
            applied_sharing_mode=SharingMode.SUMMARY_ONLY,
            transform_type=PolicyTransformType.SUMMARY_ONLY,
        ),
    )


def build_aggregate_submit(
    create_message: TaskCreateMessage,
    *,
    participant_id: str,
    summary: str,
    provenance_ref: str | None = None,
    source_refs: list[SourceRef] | None = None,
) -> AggregateSubmitMessage:
    """Return a valid aggregate-submit message derived from a task-create run."""
    return AggregateSubmitMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_AGGREGATE_SUBMIT,
            task_id=create_message.envelope.task_id,
            run_id=create_message.envelope.run_id,
            message_id=new_message_id(),
            sender_id=participant_id,
            recipient_id="coordinator",
            domain_id=participant_id,
            trace_id=create_message.envelope.trace_id,
            timestamp=utc_now(),
        ),
        payload=AggregateSubmitPayload(
            participant_id=participant_id,
            contribution_type=AggregateContributionType.SUMMARY,
            summary=summary,
            provenance_ref=provenance_ref,
            source_refs=[] if source_refs is None else source_refs,
        ),
    )


def test_summary_merge_aggregation_over_one_completed_participant() -> None:
    """A single aggregate submission should produce a one-participant canonical result."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_docs",
            summary="[SUMMARY ONLY] Matched docs: Privacy Policy Memo",
            source_refs=[
                SourceRef(
                    participant_id="participant_docs",
                    source_id="doc-002",
                    source_title="Privacy Policy Memo",
                    source_path="examples/local_docs/data/doc-002__privacy-policy-memo.json",
                )
            ],
        )
    )

    result = aggregate_run_summary_merge(create_message.envelope.run_id, store=store)

    assert result.envelope.message_type == MessageType.FAP_AGGREGATE_RESULT
    assert result.payload.aggregation_mode == AggregationMode.SUMMARY_MERGE
    assert result.payload.participant_count == 1
    assert (
        result.payload.final_answer
        == "[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo"
    )
    assert result.payload.source_refs[0].source_id == "doc-002"


def test_summary_merge_aggregation_over_two_completed_participants() -> None:
    """Two aggregate submissions should merge into a deterministic answer."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_docs",
            summary="[SUMMARY ONLY] Matched docs: Privacy Policy Memo",
        )
    )
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_kb",
            summary="[SUMMARY ONLY] Matched KB entries: Privacy controls",
        )
    )

    result = aggregate_run_summary_merge(create_message.envelope.run_id, store=store)

    assert result.payload.participant_count == 2
    assert result.payload.final_answer == (
        "[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo\n"
        "[participant_kb] [SUMMARY ONLY] Matched KB entries: Privacy controls"
    )


def test_summary_merge_aggregation_over_three_completed_participants() -> None:
    """Three aggregate submissions should merge into a deterministic answer."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_logs",
            summary="[SUMMARY ONLY] Matched log events: privacy-monitor",
        )
    )
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_kb",
            summary="[SUMMARY ONLY] Matched KB entries: Privacy controls",
        )
    )
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_docs",
            summary="[SUMMARY ONLY] Matched docs: Privacy Policy Memo",
        )
    )

    result = aggregate_run_summary_merge(create_message.envelope.run_id, store=store)

    assert result.payload.participant_count == 3
    assert result.payload.final_answer == (
        "[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo\n"
        "[participant_kb] [SUMMARY ONLY] Matched KB entries: Privacy controls\n"
        "[participant_logs] [SUMMARY ONLY] Matched log events: privacy-monitor"
    )


def test_summary_merge_prefers_recorded_aggregate_submissions() -> None:
    """Aggregation should use aggregate submissions before raw completed summaries."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)
    store.record_task_complete(
        build_task_complete(
            create_message,
            participant_id="participant_docs",
            summary="[SUMMARY ONLY] Old completion summary",
        )
    )
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_docs",
            summary="[SUMMARY ONLY] Submission summary",
        )
    )

    result = aggregate_run_summary_merge(create_message.envelope.run_id, store=store)

    assert result.payload.final_answer == (
        "[participant_docs] [SUMMARY ONLY] Submission summary"
    )


def test_summary_merge_uses_deterministic_participant_ordering_from_submissions() -> None:
    """Aggregation should sort aggregate submissions by participant id."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_kb",
            summary="[SUMMARY ONLY] Matched KB entries: Privacy controls",
        )
    )
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_logs",
            summary="[SUMMARY ONLY] Matched log events: privacy-monitor",
        )
    )
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_docs",
            summary="[SUMMARY ONLY] Matched docs: Privacy Policy Memo",
        )
    )

    result = aggregate_run_summary_merge(create_message.envelope.run_id, store=store)

    assert result.payload.final_answer.startswith(
        "[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo"
    )
    assert result.payload.final_answer.endswith(
        "[participant_logs] [SUMMARY ONLY] Matched log events: privacy-monitor"
    )


def test_provenance_refs_come_from_recorded_aggregate_submissions() -> None:
    """Aggregation provenance refs should prefer submission provenance refs."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    docs_attest_id = new_message_id()
    kb_attest_id = new_message_id()
    store.record_task_create(create_message)
    store.record_policy_attest(
        build_policy_attest(
            create_message,
            participant_id="participant_kb",
            policy_ref="policy.kb.v0",
            message_id=new_message_id(),
        )
    )
    store.record_policy_attest(
        build_policy_attest(
            create_message,
            participant_id="participant_docs",
            policy_ref="policy.docs.v0",
            message_id=new_message_id(),
        )
    )
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_kb",
            summary="[SUMMARY ONLY] Matched KB entries: Privacy controls",
            provenance_ref=kb_attest_id,
        )
    )
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_docs",
            summary="[SUMMARY ONLY] Matched docs: Privacy Policy Memo",
            provenance_ref=docs_attest_id,
        )
    )

    result = aggregate_run_summary_merge(create_message.envelope.run_id, store=store)

    assert result.payload.provenance_refs == [docs_attest_id, kb_attest_id]


def test_source_refs_merge_and_deduplicate_deterministically() -> None:
    """Aggregation should merge source refs in participant order and drop exact duplicates."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    shared_ref = SourceRef(
        participant_id="participant_docs",
        source_id="doc-002",
        source_title="Privacy Policy Memo",
        source_path="examples/local_docs/data/doc-002__privacy-policy-memo.json",
    )
    kb_ref = SourceRef(
        participant_id="participant_kb",
        source_id="kb-001",
        source_title="Privacy controls",
        source_path="examples/local_kb/data/kb-001__privacy-controls.json",
    )
    store.record_task_create(create_message)
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_kb",
            summary="[SUMMARY ONLY] Matched KB entries: Privacy controls",
            source_refs=[kb_ref],
        )
    )
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_docs",
            summary="[SUMMARY ONLY] Matched docs: Privacy Policy Memo",
            source_refs=[shared_ref, shared_ref],
        )
    )

    result = aggregate_run_summary_merge(create_message.envelope.run_id, store=store)

    assert [(source_ref.participant_id, source_ref.source_id) for source_ref in result.payload.source_refs] == [
        ("participant_docs", "doc-002"),
        ("participant_kb", "kb-001"),
    ]


def test_no_fallback_from_completed_participants_when_submissions_are_absent() -> None:
    """Aggregation should fail when only completions exist and no aggregate submissions were recorded."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)
    store.record_task_complete(
        build_task_complete(
            create_message,
            participant_id="participant_docs",
            summary="[SUMMARY ONLY] Matched docs: Privacy Policy Memo",
        )
    )

    with pytest.raises(NoCompletedParticipantsError, match="No completed participant results"):
        aggregate_run_summary_merge(create_message.envelope.run_id, store=store)


def test_aggregate_result_preserves_original_task_run_and_trace_ids() -> None:
    """Aggregate results should preserve the original run context."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_docs",
            summary="[SUMMARY ONLY] Matched docs: Privacy Policy Memo",
        )
    )

    result = aggregate_run_summary_merge(create_message.envelope.run_id, store=store)

    assert result.envelope.task_id == create_message.envelope.task_id
    assert result.envelope.run_id == create_message.envelope.run_id
    assert result.envelope.trace_id == create_message.envelope.trace_id


def test_recording_aggregate_result_updates_status_message_count_and_last_message_type() -> None:
    """Recording an aggregate result should update the stored run projection."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    task_complete = build_task_complete(
        create_message,
        participant_id="participant_docs",
        summary="[SUMMARY ONLY] Matched docs: Privacy Policy Memo",
    )
    policy_attest = build_policy_attest(
        create_message,
        participant_id="participant_docs",
        policy_ref="policy.docs.v0",
    )
    store.record_task_create(create_message)
    store.record_task_complete(task_complete)
    store.record_policy_attest(policy_attest)
    store.record_aggregate_submit(
        build_aggregate_submit(
            create_message,
            participant_id="participant_docs",
            summary=task_complete.payload.summary,
            provenance_ref=policy_attest.envelope.message_id,
            source_refs=[
                SourceRef(
                    participant_id="participant_docs",
                    source_id="doc-002",
                    source_title="Privacy Policy Memo",
                    source_path="examples/local_docs/data/doc-002__privacy-policy-memo.json",
                )
            ],
        )
    )
    aggregate_result = aggregate_run_summary_merge(create_message.envelope.run_id, store=store)

    snapshot = store.record_aggregate_result(aggregate_result)

    assert snapshot.status == RunStatus.AGGREGATED_RECORDED
    assert snapshot.message_count == 5
    assert snapshot.last_message_type == "fap.aggregate.result"
    assert snapshot.aggregate_results[0].aggregation_mode == AggregationMode.SUMMARY_MERGE
    assert snapshot.aggregate_results[0].source_refs[0].source_id == "doc-002"


def test_no_completed_participants_raises_expected_error() -> None:
    """Aggregation should fail cleanly when no participant completions exist."""
    store = InMemoryRunStore()
    create_message = build_create_message()
    store.record_task_create(create_message)

    with pytest.raises(NoCompletedParticipantsError, match="No completed participant results"):
        aggregate_run_summary_merge(create_message.envelope.run_id, store=store)

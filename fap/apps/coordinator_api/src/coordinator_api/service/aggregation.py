"""Deterministic aggregation helpers for coordinator runtime state."""

from __future__ import annotations

from fap_core.clocks import utc_now
from fap_core.enums import AggregateContributionType, AggregationMode, MessageType
from fap_core.ids import new_message_id
from fap_core.messages import (
    AggregateResultMessage,
    AggregateResultPayload,
    MessageEnvelope,
    SourceRef,
)

from coordinator_api.service.store import CoordinatorStore
from coordinator_api.service.state import AggregateSubmissionRecord


class AggregationRunNotFoundError(Exception):
    """Raised when aggregation targets an unknown run."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"Run not found: {run_id!r}")


class NoCompletedParticipantsError(Exception):
    """Raised when a run has no aggregate submissions to aggregate."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(f"No completed participant results available for run: {run_id!r}")


def aggregate_run_summary_merge(run_id: str, *, store: CoordinatorStore) -> AggregateResultMessage:
    """Build a canonical summary-merge aggregate result from participant aggregate submissions."""
    snapshot = store.get_run(run_id)
    task_create_message = store.get_task_create_message(run_id)
    if snapshot is None or task_create_message is None:
        raise AggregationRunNotFoundError(run_id)

    aggregate_submissions = sorted(
        [
            submission
            for submission in snapshot.aggregate_submissions
            if (
                submission.contribution_type == AggregateContributionType.SUMMARY
                and submission.summary is not None
            )
        ],
        key=lambda submission: submission.participant_id,
    )
    if not aggregate_submissions:
        raise NoCompletedParticipantsError(run_id)

    provenance_refs = [
        submission.provenance_ref
        for submission in aggregate_submissions
        if submission.provenance_ref is not None
    ]
    source_refs = _merge_source_refs(aggregate_submissions)
    final_answer = "\n".join(
        f"[{submission.participant_id}] {submission.summary}"
        for submission in aggregate_submissions
    )
    participant_count = len(aggregate_submissions)

    return AggregateResultMessage(
        envelope=MessageEnvelope(
            message_type=MessageType.FAP_AGGREGATE_RESULT,
            task_id=task_create_message.envelope.task_id,
            run_id=task_create_message.envelope.run_id,
            message_id=new_message_id(),
            sender_id="coordinator",
            recipient_id=task_create_message.envelope.sender_id,
            domain_id="coordinator",
            trace_id=task_create_message.envelope.trace_id,
            timestamp=utc_now(),
        ),
        payload=AggregateResultPayload(
            aggregation_mode=AggregationMode.SUMMARY_MERGE,
            final_answer=final_answer,
            participant_count=participant_count,
            provenance_refs=provenance_refs,
            source_refs=source_refs,
        ),
    )


def _merge_source_refs(aggregate_submissions: list[AggregateSubmissionRecord]) -> list[SourceRef]:
    """Merge and deduplicate source refs from aggregate submissions deterministically."""
    merged_source_refs: list[SourceRef] = []
    seen_refs: set[tuple[str, str, str, str]] = set()

    for submission in aggregate_submissions:
        for source_ref in submission.source_refs:
            dedupe_key = (
                source_ref.participant_id,
                source_ref.source_id,
                source_ref.source_title,
                source_ref.source_path,
            )
            if dedupe_key in seen_refs:
                continue
            seen_refs.add(dedupe_key)
            merged_source_refs.append(source_ref.model_copy(deep=True))

    return merged_source_refs

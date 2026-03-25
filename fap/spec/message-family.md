# Message Family

This document describes the currently implemented FAP message types in protocol version `0.1`.

## Runtime-Active Messages

| Message Type | Purpose | Typical Sender | Current Alpha Usage |
| --- | --- | --- | --- |
| `fap.task.create` | Request participant evaluation and possible execution of a task | Coordinator or coordinator-side wrapper | Active |
| `fap.task.accept` | Indicate a participant can handle the task | Participant | Active |
| `fap.task.reject` | Indicate a participant cannot handle the task | Participant | Active |
| `fap.task.complete` | Return the governed execution result of a participant task | Participant | Active |
| `fap.policy.attest` | Attest how participant policy was applied | Participant | Active |
| `fap.aggregate.submit` | Submit a participant-originated governed contribution for aggregation | Participant | Active |
| `fap.aggregate.result` | Return the canonical coordinator aggregation result | Coordinator | Active |
| `fap.exception` | Carry canonical exceptional conditions | Any service | Implemented, limited runtime use |

## `fap.task.create`

Purpose:
- start a coordinator-managed run
- request participant evaluation and possible execution

Payload fields:
- `title`
- `description`
- `requested_capabilities`
- `input_query`
- `constraints`
- `deadline`
- `budget`

Key constraints:
- `title`, `description`, and `input_query` must be non-empty stripped strings
- `requested_capabilities` entries must be non-empty stripped strings
- `constraints` entries must be non-empty stripped strings
- `deadline`, if present, must be timezone-aware

Currently implemented senders:
- coordinator ingress
- coordinator-side `/ask` wrapper

## `fap.task.accept`

Purpose:
- accept a task for a participant capability profile

Payload fields:
- `participant_id`
- `accepted_capabilities`
- `constraints`
- `estimated_confidence`
- `note`

Key constraints:
- `participant_id` must be non-empty
- `accepted_capabilities` and `constraints` entries must be non-empty
- `estimated_confidence`, if present, must be between `0.0` and `1.0`
- `note`, if present, must not be blank after stripping

Currently implemented senders:
- `participant_docs`
- `participant_kb`
- `participant_logs`

## `fap.task.reject`

Purpose:
- reject a task for a participant capability profile

Payload fields:
- `participant_id`
- `reason`
- `retryable`
- `details`

Key constraints:
- `participant_id` and `reason` must be non-empty
- `details`, if present, must not be blank after stripping

Currently implemented senders:
- `participant_docs`
- `participant_kb`
- `participant_logs`

## `fap.task.complete`

Purpose:
- return the governed execution outcome of a participant task

Payload fields:
- `participant_id`
- `status`
- `summary`
- `confidence`
- `result_ref`
- `source_refs`

Key constraints:
- `participant_id` and `summary` must be non-empty
- `status` is a constrained vocabulary and currently allows only:
  - `completed`
- `confidence`, if present, must be between `0.0` and `1.0`
- `result_ref`, if present, must not be blank after stripping
- `source_refs`, if present, is a list of deterministic local evidence pointers with:
  - `participant_id`
  - `source_id`
  - `source_title`
  - `source_path`

Currently implemented senders:
- `participant_docs`
- `participant_kb`
- `participant_logs`

## `fap.policy.attest`

Purpose:
- describe how participant policy transformed or constrained an export

Payload fields:
- `participant_id`
- `policy_ref`
- `original_privacy_class`
- `applied_sharing_mode`
- `transform_type`
- `attestation_note`

Key constraints:
- `participant_id` and `policy_ref` must be non-empty
- `original_privacy_class` must use the implemented privacy enum
- `applied_sharing_mode` must use the implemented sharing-mode enum
- `transform_type` is a constrained vocabulary and currently allows:
  - `raw`
  - `redacted`
  - `summary_only`
  - `vote_only`
- `attestation_note`, if present, must not be blank after stripping

Currently implemented senders:
- `participant_docs`
- `participant_kb`
- `participant_logs`

## `fap.aggregate.submit`

Purpose:
- submit a participant-originated governed contribution for coordinator aggregation

Payload fields:
- `participant_id`
- `contribution_type`
- `summary`
- `vote`
- `confidence`
- `provenance_ref`
- `source_refs`

Key constraints:
- `participant_id` must be non-empty
- `contribution_type` is a constrained vocabulary and currently allows only:
  - `summary`
- at least one of `summary` or `vote` must be present
- `confidence`, if present, must be between `0.0` and `1.0`
- `provenance_ref`, if present, must not be blank after stripping
- `source_refs`, if present, carries the same local evidence pointers included in the
  matching `fap.task.complete`

Currently implemented senders:
- `participant_docs`
- `participant_kb`
- `participant_logs`

Currently implemented runtime usage:
- emitted by participant `/execute`
- recorded by coordinator before final aggregation

## `fap.aggregate.result`

Purpose:
- return the canonical coordinator aggregation result

Payload fields:
- `aggregation_mode`
- `final_answer`
- `participant_count`
- `provenance_refs`
- `source_refs`
- `confidence`

Key constraints:
- `aggregation_mode` is a constrained vocabulary and currently allows only:
  - `summary_merge`
- `final_answer` must be non-empty
- `participant_count` must be non-negative
- `source_refs`, if present, is the deterministic merged and deduplicated list of
  participant evidence pointers collected from recorded aggregate submissions
- `confidence`, if present, must be between `0.0` and `1.0`

Currently implemented sender:
- coordinator

Currently implemented runtime usage:
- emitted by `POST /runs/{run_id}/aggregate/summary-merge`
- emitted as the final result of `POST /runs/{run_id}/orchestrate/summary-merge`
- returned by the `/ask` wrapper as the final canonical aggregate message

## `fap.exception`

Purpose:
- carry an exception or failure condition in canonical FAP form

Payload fields:
- `code`
- `message`
- `retryable`
- `details`

Key constraints:
- `code` and `message` must be non-empty
- `details`, if present, must not be blank after stripping

Currently implemented usage:
- schema and parsing support exist
- limited direct runtime use compared with the main task / governance / aggregation path

## Parsing And Codec Notes

Currently implemented behavior:

- raw dictionaries are dispatched by `(protocol, version, message_type)`
- supported protocol version is `0.1`
- supported messages are parsed through the shared registry
- canonical JSON-safe output is produced through the shared codec
- enum-backed fields serialize to the same stable wire strings shown in this document

# Coordinator State Model

This document describes the currently implemented DB-first coordinator runtime state.

## Durable Runtime State

The coordinator now uses the database as the primary runtime source of truth.

Durable tables currently implemented:

- `protocol_events`
  - one row per canonical persisted protocol message
- `run_snapshots`
  - latest materialized projection per `run_id`

Current runtime behavior:

- writes update durable state first through the coordinator store abstraction
- `GET /runs/{run_id}` reads from the persisted run snapshot
- `GET /runs/{run_id}/events` reads from persisted protocol events
- dispatch, orchestration, and aggregation recover run context from durable state
- the old in-memory store remains only as a compatibility/test fallback

## Run Snapshot Fields

The coordinator currently tracks the following per-run fields:

| Field | Meaning |
| --- | --- |
| `run_id` | Coordinator run identifier |
| `task_id` | Task identifier associated with the run |
| `status` | Current high-level lifecycle marker |
| `created_message_id` | Message id of the original `fap.task.create` |
| `last_message_type` | Most recently recorded tracked message type |
| `message_count` | Number of tracked messages recorded in the run |
| `accepted_participants` | Participant ids that have accepted the task |
| `rejected_participants` | Structured rejection entries |
| `completed_participants` | Structured completion entries |
| `policy_attestations` | Structured policy attestation entries |
| `aggregate_submissions` | Structured participant-originated aggregation inputs |
| `aggregate_results` | Structured aggregate result entries |

## Status Vocabulary

`status` is now a constrained coordinator vocabulary with the following currently implemented values:

| Status | Meaning |
| --- | --- |
| `created` | Original `fap.task.create` recorded |
| `decisions_recorded` | At least one `fap.task.accept` or `fap.task.reject` recorded |
| `completed_recorded` | At least one `fap.task.complete` recorded |
| `aggregated_recorded` | At least one `fap.aggregate.result` recorded |

## Structured Projection Entries

### `rejected_participants`

Each entry currently includes:

- `participant_id`
- `reason`
- `retryable`

### `completed_participants`

Each entry currently includes:

- `participant_id`
- `status`
- `summary`
- `message_id`
- `source_refs`

`status` is currently constrained to:

- `completed`

### `policy_attestations`

Each entry currently includes:

- `participant_id`
- `policy_ref`
- `original_privacy_class`
- `applied_sharing_mode`
- `transform_type`
- `message_id`

`transform_type` currently uses the constrained policy-transform vocabulary:

- `raw`
- `redacted`
- `summary_only`
- `vote_only`

### `aggregate_submissions`

Each entry currently includes:

- `participant_id`
- `contribution_type`
- `summary`
- `vote`
- `confidence`
- `provenance_ref`
- `source_refs`
- `message_id`

`contribution_type` is currently constrained to:

- `summary`

### `aggregate_results`

Each entry currently includes:

- `aggregation_mode`
- `final_answer`
- `participant_count`
- `provenance_refs`
- `source_refs`
- `message_id`

`aggregation_mode` is currently constrained to:

- `summary_merge`

## Message Recording Behavior

### When `fap.task.create` is recorded

- a new durable run snapshot is created
- duplicate `run_id` is rejected
- the original canonical `TaskCreateMessage` is retained durably for later dispatch and orchestration recovery
- `status = created`

### When `fap.task.accept` is recorded

- the run must already exist
- the participant id is added to `accepted_participants` if not already present
- `status = decisions_recorded`
- `last_message_type` and `message_count` update

### When `fap.task.reject` is recorded

- the run must already exist
- a structured rejection entry is appended
- `status = decisions_recorded`
- `last_message_type` and `message_count` update

### When `fap.task.complete` is recorded

- the run must already exist
- a structured completion entry is appended
- any participant-local `source_refs` are preserved in the completion projection
- `status = completed_recorded`
- `last_message_type` and `message_count` update

### When `fap.policy.attest` is recorded

- the run must already exist
- a structured attestation entry is appended
- `last_message_type` and `message_count` update

### When `fap.aggregate.submit` is recorded

- the run must already exist
- a structured aggregate-submission entry is appended
- participant-originated `message_id` and `provenance_ref` are preserved
- participant-originated `source_refs` are preserved
- `last_message_type` and `message_count` update

### When `fap.aggregate.result` is recorded

- the run must already exist
- a structured aggregate-result entry is appended
- merged and deduplicated `source_refs` from aggregate submissions are preserved
- `status = aggregated_recorded`
- `last_message_type` and `message_count` update

## Coordinator Routes Using This State

Currently implemented coordinator routes that depend on durable state:

- `POST /messages`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/events`
- `POST /runs/{run_id}/dispatch/participant-docs`
- `POST /runs/{run_id}/dispatch/participant-docs/execute`
- `POST /runs/{run_id}/dispatch/participant-kb`
- `POST /runs/{run_id}/dispatch/participant-kb/execute`
- `POST /runs/{run_id}/dispatch/participant-logs`
- `POST /runs/{run_id}/dispatch/participant-logs/execute`
- `POST /runs/{run_id}/aggregate/summary-merge`
- `POST /runs/{run_id}/orchestrate/summary-merge`
- `POST /ask`

## Not Yet Implemented In v0.1 Alpha

- replay engine / durable state rebuild from events
- cryptographic auth and stronger trust verification
- richer aggregation state and modes beyond `summary_merge`
- cross-version runtime state management beyond protocol `0.1`
- distributed coordinator workers or background scheduling

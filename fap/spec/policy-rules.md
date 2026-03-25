# Policy Rules

This document describes the deterministic policy behavior currently implemented in the shared FAP policy engine.

## Scope

The current alpha policy engine is:

- deterministic
- local
- synchronous
- prefix-based for transformed text

There is no LLM summarization in v0.1 alpha.

## Rule Matrix

| Privacy Class | Requested `raw` | Requested `redacted` | Requested `summary_only` | Requested `vote_only` |
| --- | --- | --- | --- | --- |
| `public` | `raw` | `redacted` | `summary_only` | `vote_only` |
| `internal` | `redacted` | `redacted` | `summary_only` | `vote_only` |
| `sensitive` | `summary_only` | `summary_only` | `summary_only` | `vote_only` |
| `restricted` | `vote_only` | `vote_only` | `vote_only` | `vote_only` |

## Transform Behavior

### `raw`

- content is returned unchanged
- `redactions_applied = false`

### `redacted`

Currently implemented behavior:

- default transform: `[REDACTED EXPORT] <content>`
- `redactions_applied = true`

Special case currently implemented:

- `public + redacted` keeps content unchanged and sets `redactions_applied = false`

### `summary_only`

- content becomes `[SUMMARY ONLY] <content>`
- `redactions_applied = false`

### `vote_only`

- exported content becomes `null`
- `redactions_applied = false`

## Policy Attestation

Each policy decision currently produces a canonical `fap.policy.attest` message containing:

- `participant_id`
- `policy_ref`
- `original_privacy_class`
- `applied_sharing_mode`
- `transform_type`
- optional downgrade note when the applied sharing mode differs from the requested sharing mode

## Envelope Context Behavior

The shared policy engine currently supports optional attestation envelope context.

If envelope context is not provided:

- the attestation uses fresh `task_id`, `run_id`, and `trace_id`
- sender defaults to the participant id
- recipient defaults to `coordinator`

If envelope context is provided:

- the attestation preserves the provided `task_id`
- the attestation preserves the provided `run_id`
- the attestation preserves the provided `trace_id`
- the attestation preserves the provided sender, recipient, and domain fields
- `message_id` is still fresh

This envelope-context behavior is what allows governed execution messages to remain correlated to the same FAP run in the current alpha.

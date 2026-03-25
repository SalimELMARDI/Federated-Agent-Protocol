# participant_docs Evaluation Flow

This document describes the currently implemented `participant_docs /evaluate` flow in v0.1 alpha.

## Endpoint

- `POST /evaluate`

## Expected Inbound Message

Currently implemented input:

- canonical FAP JSON object with top-level `envelope` and `payload`
- parsed through the shared FAP parser
- only `fap.task.create` is supported for evaluation

If the inbound valid FAP message is not `fap.task.create`, `participant_docs` returns:

```json
{
  "detail": {
    "code": "unsupported_evaluation_message",
    "message": "participant_docs can only evaluate 'fap.task.create' messages"
  }
}
```

Malformed known-kind messages use the shared parse error mapping and currently return HTTP `422` with `code = "invalid_message"`.

## Supported Capability Set

`participant_docs` currently supports exactly:

- `docs.search`
- `docs.lookup`
- `docs.summarize`

## Evaluation Rules

### Accept

`participant_docs` returns `fap.task.accept` when:

- `requested_capabilities` is empty
- every requested capability is supported

Current accept behavior:

- when `requested_capabilities` is empty, `accepted_capabilities` becomes the full supported set in declared order
- when all requested capabilities are supported, `accepted_capabilities` preserves the inbound order

### Reject

`participant_docs` returns `fap.task.reject` when one or more requested capabilities are unsupported.

Current reject behavior:

- `reason` lists the unsupported capabilities
- `retryable` is `false`

## Response Message Correlation

Currently implemented response envelope behavior:

- `task_id` preserved from inbound task
- `run_id` preserved from inbound run
- `trace_id` preserved from inbound trace
- `sender_id = "participant_docs"`
- `recipient_id = inbound sender_id`
- `domain_id = "participant_docs"`
- fresh `message_id`
- current UTC timestamp

## Current Alpha Scope Note

This flow is implemented specifically for `participant_docs`. It is not yet generalized across `participant_logs` or `participant_kb` in v0.1 alpha.

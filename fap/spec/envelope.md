# Message Envelope

All canonical FAP messages currently use the same top-level shape:

```json
{
  "envelope": { "...": "..." },
  "payload": { "...": "..." }
}
```

## Envelope Fields

| Field | Type | Currently Implemented Meaning |
| --- | --- | --- |
| `protocol` | string | Protocol marker. Must equal `"FAP"`. |
| `version` | string enum | Protocol version. Currently supported value is `"0.1"`. |
| `message_type` | string enum | One of the implemented FAP message kinds. |
| `task_id` | string | Correlates related task messages. |
| `run_id` | string | Correlates a coordinator-tracked run. |
| `message_id` | string | Unique identifier for the individual message. |
| `sender_id` | string | Logical sender of the message. |
| `recipient_id` | string | Intended recipient. |
| `domain_id` | string | Sender-side domain identifier. |
| `trace_id` | string | Cross-message correlation identifier. |
| `timestamp` | datetime | Time the message was created. |
| `governance` | object or null | Optional governance metadata. |

## Governance Metadata Fields

| Field | Type | Currently Implemented Meaning |
| --- | --- | --- |
| `privacy_class` | enum or null | `public`, `internal`, `sensitive`, or `restricted` |
| `sharing_mode` | enum or null | `raw`, `redacted`, `summary_only`, or `vote_only` |
| `policy_ref` | string or null | Policy reference used for governed export |
| `provenance_ref` | string or null | Optional provenance reference |

## Validation Rules Currently Enforced

- `protocol` must equal `"FAP"`
- `version` must be a supported protocol version enum value
- current supported version is only `"0.1"`
- `message_type` must be a supported message enum value
- `task_id`, `run_id`, `message_id`, `sender_id`, `recipient_id`, `domain_id`, and `trace_id` must be non-empty stripped strings
- `timestamp` must be timezone-aware
- extra fields are forbidden on both the envelope and governance metadata

## Version-Aware Dispatch Behavior

Currently implemented parsing and dispatch explicitly uses:

- `protocol`
- `version`
- `message_type`

The runtime dispatch key is effectively:

```text
(protocol, version, message_type)
```

Current behavior:

- `protocol` must be `"FAP"`
- `version` must be `"0.1"`
- if `version` is unsupported, parsing fails clearly with an unsupported-version error
- if `message_type` is unknown within supported version `0.1`, parsing fails with the unsupported-message-kind error family
- if the message kind is known but the payload is malformed, parsing fails with the invalid-message error family

This is release-hardening behavior for the alpha runtime. It is not yet a multi-version compatibility strategy beyond `0.1`.

## Provenance Correlation Expectations

For same-run messages in the current alpha:

- `task_id` remains constant across the related task lifecycle
- `run_id` remains constant across the related coordinator-managed run
- `trace_id` remains constant across the related message exchange

This correlation is currently implemented for:

- `fap.task.create`
- `fap.task.accept`
- `fap.task.reject`
- `fap.task.complete`
- `fap.policy.attest`
- `fap.aggregate.submit`
- `fap.aggregate.result`

In particular:

- participant `/execute` preserves inbound `task_id`, `run_id`, and `trace_id` when emitting `task_complete`, `policy_attest`, and `aggregate_submit`
- coordinator aggregation preserves the original run context when emitting `aggregate_result`

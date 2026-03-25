# Identity And Trust

This document describes the currently implemented trust and identity posture for the FAP v0.1 alpha reference runtime.

## Current Trusted Identities

Canonical trusted participant ids currently supported:

- `participant_docs`
- `participant_kb`
- `participant_logs`

Canonical coordinator id:

- `coordinator`

Currently implemented participant trust assumption:

- each trusted participant uses the same value for `sender_id` and `domain_id`
- for example, `participant_docs` is expected to emit:
  - `sender_id = "participant_docs"`
  - `domain_id = "participant_docs"`

## Coordinator Trusted Participant Registry

The coordinator now has an explicit centralized trusted participant registry for the current alpha participants.

For each trusted participant, the coordinator knows:

- participant id
- expected `domain_id`
- configured evaluate endpoint URL
- configured execute endpoint URL

This registry is used by the normal runtime path for:

- dispatch to `/evaluate`
- dispatch to `/execute`
- one-shot orchestration
- `/ask`, which reuses orchestration

## What Is Enforced Now

When the coordinator dispatches to a participant and receives canonical FAP responses, it validates response identity consistency.

### Evaluate Response Checks

For `fap.task.accept` or `fap.task.reject`, the coordinator verifies:

- `envelope.sender_id` matches the expected trusted participant id
- `envelope.domain_id` matches the expected trusted participant domain id
- `envelope.recipient_id` matches the original task sender context carried by the stored `fap.task.create`
- `payload.participant_id` matches the expected trusted participant id

### Execute Response Checks

For returned:

- `fap.task.complete`
- `fap.policy.attest`
- `fap.aggregate.submit`

the coordinator verifies for each message:

- `envelope.sender_id` matches the expected trusted participant id
- `envelope.domain_id` matches the expected trusted participant domain id
- `envelope.recipient_id` matches the original task sender context carried by the stored `fap.task.create`
- `payload.participant_id` matches the expected trusted participant id

If any of these checks fail, the coordinator rejects the downstream response as a trust/identity failure.

## Failure Behavior

Currently implemented failure behavior:

- dispatch routes return HTTP `502`
- error code:
  - `participant_identity_mismatch`
- message text includes the expected participant identity and the mismatched values actually returned

One-shot orchestration inherits the same checks because it reuses dispatch. Identity mismatch failures therefore also surface through orchestration as HTTP `502 participant_identity_mismatch`.

## What This Is Not

This release hardening step is not cryptographic authentication.

Not yet implemented:

- message signatures
- API keys
- mTLS
- JWTs
- certificate pinning
- external trust registries
- attested workload identity

The current model is identity consistency validation against a coordinator-side trusted registry, not proof of identity in a cryptographic sense.

## Why This Exists

This step reduces ambiguity before release by making the runtime explicit about which participant identities it trusts and by rejecting obvious response spoofing or routing inconsistencies early.

It improves release posture without changing the protocol schema or introducing auth infrastructure that does not yet exist.

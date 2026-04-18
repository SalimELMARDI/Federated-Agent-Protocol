# Identity And Trust

This document describes the currently implemented trust and identity posture for the FAP v0.1
alpha reference runtime.

## Current Trusted Identities

Canonical participant ids currently supported by the runtime:

- `participant_docs`
- `participant_kb`
- `participant_logs`
- `participant_llm` when explicitly configured into the coordinator

Canonical coordinator id:

- `coordinator`

Currently implemented participant trust assumption:

- each trusted participant uses the same value for `sender_id` and `domain_id`
- for example, `participant_docs` is expected to emit:
  - `sender_id = "participant_docs"`
  - `domain_id = "participant_docs"`

## Execution Classes And Trust Posture

The current runtime now has an execution-class distinction that matters for trust posture:

- `local`
  - `participant_docs`
  - `participant_kb`
  - `participant_logs`
- `outbound`
  - `participant_llm`

For local participants, the current trust story is strongest: raw source data stays within the
participant boundary and only governed exports leave the participant.

For the outbound participant, the trust story is weaker by design: raw `input_query` content is
sent to an external or local-model API before governance is applied to the returned content. That
execution class difference should be treated as part of the protocol posture, not as an
implementation detail.

## Coordinator Trusted Participant Registry

The coordinator has an explicit centralized trusted participant registry.

For each trusted participant, the coordinator knows:

- participant id
- expected `domain_id`
- configured evaluate endpoint URL
- configured execute endpoint URL

This registry is used by the normal runtime path for:

- dispatch to `/evaluate`
- dispatch to `/execute`
- participant discovery through `/profile` and `/status`
- one-shot orchestration
- `/ask`, which reuses orchestration

## What Is Enforced Now

When the coordinator dispatches to a participant and receives canonical FAP responses, it validates
response identity consistency.

### Evaluate Response Checks

For `fap.task.accept` or `fap.task.reject`, the coordinator verifies:

- `envelope.sender_id` matches the expected trusted participant id
- `envelope.domain_id` matches the expected trusted participant domain id
- `envelope.recipient_id` matches the original task sender context carried by the stored
  `fap.task.create`
- `payload.participant_id` matches the expected trusted participant id

### Execute Response Checks

For returned:

- `fap.task.complete`
- `fap.policy.attest`
- `fap.aggregate.submit`

the coordinator verifies for each message:

- `envelope.sender_id` matches the expected trusted participant id
- `envelope.domain_id` matches the expected trusted participant domain id
- `envelope.recipient_id` matches the original task sender context carried by the stored
  `fap.task.create`
- `payload.participant_id` matches the expected trusted participant id

### Discovery Response Checks

For returned:

- `fap.participant.profile`
- `fap.participant.status`

the coordinator verifies:

- `envelope.sender_id`
- `envelope.domain_id`
- `envelope.recipient_id`
- `payload.participant_id`
- `payload.domain_id`

against the trusted participant registry.

If any of these checks fail, the coordinator rejects the downstream response as a trust or identity
failure.

## Failure Behavior

Currently implemented failure behavior:

- dispatch routes return HTTP `502`
- discovery failures return HTTP `502`
- error codes include:
  - `participant_identity_mismatch`
  - `participant_discovery_failed`
  - `invalid_participant_discovery`

Message text includes the expected participant identity and the mismatched values actually
returned.

One-shot orchestration inherits the same checks because it reuses dispatch. Identity mismatch
failures therefore also surface through orchestration as HTTP `502 participant_identity_mismatch`.

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

The current model is identity consistency validation against a coordinator-side trusted registry,
not proof of identity in a cryptographic sense.

## Why This Exists

This step reduces ambiguity by making the runtime explicit about which participant identities it
trusts and by rejecting obvious response spoofing or routing inconsistencies early.

It improves alpha posture without pretending auth infrastructure already exists.

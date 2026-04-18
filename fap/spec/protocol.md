# Protocol Overview

## Purpose

FAP defines the protocol layer for governed federated work across private domains. A coordinator can
request work, participants can evaluate whether they can perform it, participants execute work
inside their own domain boundary, and only governed exports leave the participant.

The current alpha is no longer only a schema reference. It includes a working DB-first coordinator,
local participants, an optional outbound participant, active aggregation, participant-originated
`fap.aggregate.submit`, durable protocol state, and a thin `/ask` wrapper on top of the core
runtime.

## What FAP Guarantees In v0.1 Alpha

The current alpha is built around a few explicit guarantees:

- the coordinator is authoritative for run creation, dispatch, aggregation, and durable run state
- governance is a protocol-level control point, not only participant-local application logic
- participants emit typed, versioned FAP messages rather than arbitrary JSON payloads
- aggregation is explicit and participant-originated through `fap.aggregate.submit`
- evidence pointers can survive the workflow through structured `source_refs`
- participant class affects trust posture and should be visible at the protocol surface

These guarantees are the current identity of the protocol.

## What FAP Is Not Trying To Be In v0.1 Alpha

FAP is deliberately not trying to be any of the following in this release:

- a peer-to-peer A2A protocol
- a general-purpose agent framework
- a production-ready trust fabric with signatures, mTLS, or external identity authorities
- a fully decentralized multi-agent network

Those directions may matter later, but they are intentionally out of scope for the current alpha.

## Why Coordinator-Managed Federation Is The Design Center

The design center of FAP today is coordinator-managed federation across participant boundaries.

That means:

- participants keep control of local execution
- the coordinator remains authoritative for run state and aggregation
- governance and identity checks remain visible in one place
- the system stays inspectable through durable events and snapshots

This is the current design center because it makes the protocol understandable, testable, and
honest about trust boundaries.

## Roles

### Coordinator

The coordinator:

- receives canonical FAP messages
- persists protocol events and latest run snapshots
- dispatches stored `fap.task.create` runs to trusted participants for evaluation and execution
- validates participant response identity consistency
- discovers trusted participant profiles and status over canonical FAP messages
- aggregates participant-originated submissions into canonical `fap.aggregate.result`

### Participant

A participant:

- receives canonical FAP messages
- evaluates whether it can perform the requested work
- executes work inside its own domain
- applies the shared policy engine
- advertises profile and status metadata over canonical FAP messages
- returns governed protocol messages back to the coordinator

Currently implemented runtime participants:

- `participant_docs` (`execution_class = local`)
- `participant_kb` (`execution_class = local`)
- `participant_logs` (`execution_class = local`)
- `participant_llm` (`execution_class = outbound`, optional and explicitly opt-in)

## Core Principles

### Protocol-first

The shared protocol is centralized in `packages/fap_core`. Message validation, parsing,
version-aware dispatch, and canonical serialization are defined there rather than in
service-specific code.

### Local execution

Participant-side data access stays local to the participant unless the participant's execution
class explicitly says otherwise. In the current alpha:

- `participant_docs` reads participant-local documents from disk
- `participant_logs` reads participant-local log events from disk
- `participant_kb` reads participant-local knowledge-base entries from disk
- `participant_llm` is the explicit exception: it is an outbound participant and sends raw
  `input_query` content to an external or local-model API before governance is applied to the
  returned content

### Governed export

Participants do not export arbitrary local results directly. The current alpha uses a shared
deterministic policy engine to transform a participant-local result into:

- an approved export
- a canonical `fap.policy.attest`
- a participant-originated `fap.aggregate.submit`

### Provenance and correlation

Same-run messages preserve the originating `task_id`, `run_id`, and `trace_id`. This is currently
implemented for:

- participant evaluation responses
- participant task completion responses
- participant policy attestations
- participant aggregate submissions
- coordinator aggregate results

The alpha runtime also carries optional structured `source_refs` through execution and aggregation
payloads. These refs are deterministic explainability pointers derived by each participant and can
identify the local file, KB entry, log file, or provider provenance that informed the governed
export.

`source_refs` are not cryptographic attestations. They are explainability-oriented pointers with
the current reference-runtime shape:

- `participant_id`
- `source_id`
- `source_title`
- `source_path`

### Identity consistency before cryptographic auth

The alpha runtime includes explicit trusted participant identities and coordinator-side response
validation. The coordinator verifies that dispatch responses come from the expected participant
sender/domain identity and target the expected recipient context.

This is release hardening, not full authentication. See `identity-and-trust.md`.

## Alpha Scope

Currently implemented in v0.1 alpha:

- shared envelope and governance metadata
- version-aware dispatch over `(protocol, version, message_type)`
- supported protocol version `0.1`
- canonical codec and typed registry
- DB-first coordinator runtime
- durable `protocol_events` and `run_snapshots`
- participant evaluation for docs, kb, logs, and optional llm
- participant governed execution for docs, kb, logs, and optional llm
- participant-originated `fap.aggregate.submit`
- coordinator `summary_merge` aggregation
- structured `source_refs` in `fap.task.complete`, `fap.aggregate.submit`, and
  `fap.aggregate.result`
- one-shot orchestration
- `/ask` wrapper on top of orchestration
- trusted participant identity consistency checks
- canonical participant discovery messages and coordinator discovery endpoint

Deliberately deferred in v0.1 alpha:

- cryptographic signatures
- API keys
- mTLS
- JWT-based auth
- external trust authority integration
- replay engine
- richer aggregation modes
- multi-version protocol support beyond `0.1`
- A2A support

## Scope Boundaries

- MCP is participant-local capability and data access, not a wire-level FAP message family.
- The intended direction is MCP-inside-participants and FAP-between-domain-agents.
- A2A is not part of FAP v0.1 alpha.

# Protocol Overview

## Purpose

FAP defines the protocol layer for governed federated work across private domains. A coordinator can request work, participants can evaluate whether they can perform it, participants execute local work inside their own domains, and only governed exports leave the participant boundary.

The current alpha is no longer just a schema reference. It includes a working DB-first coordinator, three real participants, active aggregation, participant-originated `fap.aggregate.submit`, and a thin `/ask` wrapper on top of the core runtime.

The current runtime now also includes canonical participant discovery metadata through
`fap.participant.profile` and `fap.participant.status`, which is the first concrete step toward
routable domain agents rather than only opaque connectors.

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
- executes local work inside its own domain
- applies the shared policy engine
- advertises profile and status metadata over canonical FAP messages
- returns governed protocol messages back to the coordinator

Currently implemented participants:

- `participant_docs`
- `participant_kb`
- `participant_logs`

## Core Principles

### Protocol-first

The shared protocol is centralized in `packages/fap_core`. Message validation, parsing, version-aware dispatch, and canonical serialization are defined there rather than in service-specific code.

### Local execution

Participant-side data access stays local to the participant. In the current alpha:

- `participant_docs` reads participant-local documents from disk
- `participant_logs` reads participant-local log events from disk
- `participant_kb` reads participant-local knowledge-base entries from disk

### Governed export

Participants do not export arbitrary local results directly. The current alpha uses a shared deterministic policy engine to transform a participant-local result into:

- an approved export
- a canonical `fap.policy.attest`
- a participant-originated `fap.aggregate.submit`

### Provenance and correlation

Same-run messages preserve the originating `task_id`, `run_id`, and `trace_id`. This is currently implemented for:

- participant evaluation responses
- participant task completion responses
- participant policy attestations
- participant aggregate submissions
- coordinator aggregate results

The alpha runtime now also carries optional structured `source_refs` through execution and
aggregation payloads. These refs are deterministic local evidence pointers derived by each
participant connector and can identify the underlying local document, KB entry, or log file
that informed the governed export.

`source_refs` are not cryptographic attestations. They are explainability-oriented pointers with
the current reference-runtime shape:

- `participant_id`
- `source_id`
- `source_title`
- `source_path`

### Identity consistency before cryptographic auth

The alpha runtime now includes explicit trusted participant identities and coordinator-side response validation. The coordinator verifies that dispatch responses come from the expected participant sender/domain identity and target the expected recipient context.

This is release hardening, not full authentication. See `identity-and-trust.md`.

## Alpha Scope

Currently implemented in v0.1 alpha:

- shared envelope and governance metadata
- version-aware dispatch over `(protocol, version, message_type)`
- supported protocol version `0.1`
- canonical codec and typed registry
- DB-first coordinator runtime
- durable `protocol_events` and `run_snapshots`
- participant evaluation for docs, kb, and logs
- participant governed execution for docs, kb, and logs
- participant-originated `fap.aggregate.submit`
- coordinator `summary_merge` aggregation
- structured `source_refs` in `fap.task.complete`, `fap.aggregate.submit`, and `fap.aggregate.result`
- one-shot orchestration
- `/ask` wrapper on top of orchestration
- trusted participant identity consistency checks
- canonical participant discovery messages and coordinator discovery endpoint

Not yet implemented in v0.1 alpha:

- cryptographic signatures
- API keys
- mTLS
- JWT-based auth
- external trust authority integration
- replay engine
- richer aggregation modes
- multi-version protocol support beyond `0.1`

## Scope Boundaries

- MCP is participant-local capability and data access, not a wire-level FAP message family.
- The intended direction is MCP-inside-participants and FAP-between-domain-agents.
- A2A is not part of FAP v0.1 alpha.

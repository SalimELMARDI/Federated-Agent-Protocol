# FAP v0.1 Alpha Spec

This folder contains the written protocol specification for the current implemented state of the Federated Agent Protocol (FAP) reference runtime.

FAP is a protocol-first approach for coordinating governed multi-participant work without centralizing raw private data. In the current alpha, the repository includes:

- a shared protocol core in `packages/fap_core`
- canonical message models and a shared envelope
- version-aware parsing and dispatch for protocol `FAP` version `0.1`
- a DB-first coordinator runtime with durable protocol events and run snapshots
- three real reference participants:
  - `participant_docs`
  - `participant_kb`
  - `participant_logs`
- governed participant execution with canonical `task_complete`, `policy_attest`, and participant-originated `aggregate_submit`
- coordinator-managed `aggregate_result`
- structured local `source_refs` carried through execution and aggregation payloads
- one-shot orchestration and a thin user-facing `/ask` wrapper

These docs describe what is actually implemented now. Where behavior is implementation-derived, the docs use "currently implemented". Where functionality does not yet exist, the docs mark it as "not yet implemented in v0.1 alpha".

## Contents

- `protocol.md`
  High-level overview of FAP roles, principles, and alpha scope.
- `envelope.md`
  Shared message envelope, governance metadata, and version-aware dispatch behavior.
- `message-family.md`
  Implemented message types, payload fields, and constrained vocabularies.
- `identity-and-trust.md`
  Current trusted participant identities and coordinator-side identity consistency checks.
- `participant-evaluation-flow.md`
  The current participant evaluation behavior.
- `governed-execution-flow.md`
  The current participant execute behavior and coordinator-managed execution dispatch.
- `policy-rules.md`
  Deterministic policy rules currently implemented in the shared policy engine.
- `state-model.md`
  DB-first coordinator run state, status transitions, and durable snapshot behavior.
- `v0.2-domain-agents-roadmap.md`
  Forward-looking roadmap for routable domain agents, MCP-inside-participants, and richer routing.
- `examples/`
  Canonical example JSON payloads aligned with the current runtime.

## Implemented Today

- `fap.task.create`
- `fap.task.accept`
- `fap.task.reject`
- `fap.task.complete`
- `fap.policy.attest`
- `fap.aggregate.submit`
- `fap.aggregate.result`
- `fap.exception`
- `fap.participant.profile`
- `fap.participant.status`
- canonical codec and shared parsing helpers
- explicit dispatch over `(protocol, version, message_type)`
- supported protocol version `0.1`
- coordinator message ingress, run inspection, event inspection, participant dispatch, aggregation, orchestration, and `/ask`
- durable `protocol_events` and `run_snapshots`
- deterministic governed export through the shared policy engine
- explicit trusted participant identities for:
  - `participant_docs`
  - `participant_kb`
  - `participant_logs`
- coordinator-side sender/domain/recipient consistency validation on participant dispatch responses
- source-level evidence refs in execution and aggregation payloads
- participant discovery endpoints and canonical participant profile/status messages

## Release Hardening In This Spec Revision

- envelope `version` is now part of real dispatch behavior
- unsupported protocol versions fail parsing clearly
- selected wire vocabularies are constrained to enums while preserving the same wire strings:
  - coordinator run status
  - task complete status
  - aggregate contribution type
  - aggregation mode
  - policy transform type

## Not Yet Implemented In v0.1 Alpha

- cryptographic auth, signatures, and proof-of-sender verification
- replay engine / event-sourced rebuild workflow
- protocol support for versions beyond `0.1`
- API keys, mTLS, or JWT-based trust
- richer aggregation modes beyond `summary_merge`
- background concurrency or distributed coordinator workers
- A2A support

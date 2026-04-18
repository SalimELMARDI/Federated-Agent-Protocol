# FAP Current State Report

## Executive Summary

FAP is currently in a strong `v0.1.0-alpha` state as a protocol alpha, reference runtime, and
developer preview. It is no longer only a schema proposal. The repository now contains a typed
protocol core, a DB-first coordinator, multiple real participants, explicit governed execution,
participant-originated aggregation, durable run and event inspection, source-level evidence refs,
and a canonical discovery surface for participants.

The strongest parts of the project today are:

- protocol-first semantics
- local execution with governed export
- participant-originated aggregation
- durable coordinator runtime state
- explainability through `source_refs`
- a growing participant model that is starting to become self-describing

The main gaps are:

- no cryptographic trust/authentication
- no replay engine over durable events
- no routing driven by discovery metadata yet
- only one aggregation mode: `summary_merge`
- no progress or follow-up protocol
- no participant-class-aware routing yet

The current project is already credible as an alpha. The main risk is not lack of functionality,
but architectural drift: if FAP loses focus as a governed coordination protocol across domain
boundaries, it becomes much weaker.

## Release Positioning

As documented in `README.md`, FAP is currently positioned as:

- a protocol alpha
- a reference runtime
- a developer preview
- not yet a production-ready federated platform

That positioning is accurate and should be preserved.

## Current Protocol Scope

The active message family currently includes:

- `fap.task.create`
- `fap.task.accept`
- `fap.task.reject`
- `fap.task.complete`
- `fap.policy.attest`
- `fap.aggregate.submit`
- `fap.aggregate.result`
- `fap.participant.profile`
- `fap.participant.status`
- `fap.exception`

The coordinator-managed runtime flow remains:

1. `fap.task.create`
2. participant evaluation via `accept` / `reject`
3. participant execution
4. governed export via `task.complete` + `policy.attest`
5. participant-originated `aggregate.submit`
6. coordinator `aggregate.result`

This is a good semantic core. It is clear, explainable, and already useful.

## Runtime Architecture

### Protocol Core

`packages/fap_core` contains:

- typed message models
- the shared envelope
- version-aware registry and parsing
- enums and constrained wire vocabularies
- policy rules
- identity helpers

This remains the strongest long-term asset in the project.

### Coordinator

The coordinator runtime is DB-first and persists:

- `protocol_events`
- `run_snapshots`

Important coordinator qualities:

- durable run and event inspection is real
- orchestration is explicit
- aggregation is explicit
- `/ask` is only a wrapper over the governed runtime, not a separate hidden path

### Participants

The repo currently includes:

- `participant_docs`
- `participant_kb`
- `participant_logs`
- `participant_llm`

The first three are local reference participants over local data sources.

`participant_llm` is different. It is an optional outbound LLM-backed participant and must be
treated as a separate execution class, not as simply "another local participant."

### External Integration Surfaces

The runtime includes:

- `fap_client`
- `fap_mcp`

This means FAP is already externally consumable, not only internally demoable.

## What Is Strong

### 1. Protocol-first coordination

The semantic core is in typed canonical messages, not hidden coordinator glue. That gives the
runtime a much cleaner long-term foundation than many ad hoc multi-agent systems.

### 2. Governed local execution

FAP has a credible story around:

- local participant-side work
- policy before export
- explicit attestation of the transform

That is one of the most important reasons the protocol matters.

### 3. Participant-originated aggregation

`fap.aggregate.submit` is an especially good design choice. It prevents the coordinator from
quietly inventing aggregation input off the wire and keeps the coordination path visible.

### 4. Durable state

The DB-first coordinator is a real strength. The protocol is inspectable after the fact, which is
important for explainability, operational visibility, and later replay work.

### 5. Source-level evidence refs

`source_refs` make results materially more useful. They are not cryptographic proof, but they do
give users and downstream systems a visible link back to the participant-local sources that
informed the result.

### 6. Participant discovery has begun

The addition of:

- `fap.participant.profile`
- `fap.participant.status`

is the first concrete step toward discoverable domain agents rather than only fixed connectors.

## What Is Weak Or Missing

### 1. Trust/authentication is still shallow

Current trust is identity consistency validation against a coordinator-side trusted registry.

This is useful release hardening, but it is not proof of identity. Missing pieces include:

- message signatures
- mTLS
- JWT or equivalent runtime auth
- external trust authority integration

### 2. Replay and recovery are missing

The coordinator persists events and snapshots, but there is still no true replay engine or
event-sourced rebuild flow.

### 3. Routing is not yet discovery-driven

Profile/status discovery exists, but the coordinator still does not make first-class routing
decisions from:

- participant capabilities
- health
- execution class
- privacy/cost/latency posture

The runtime is discovery-aware, not yet discovery-driven.

### 4. Aggregation is still very limited

Only `summary_merge` exists today. This is sufficient for alpha, but not a long-term aggregation
story.

### 5. Evidence typing is too flat

`source_refs` currently mix different semantics under one shape. The protocol does not yet
distinguish between:

- local source evidence
- tool output
- model-generated output
- external provider provenance

### 6. No task progress / follow-up turns

There is no current protocol support for:

- participant progress updates
- coordinator-mediated follow-up turns
- iterative case refinement

These will matter a lot once participants become more agentic.

## Current Inconsistencies And Risks

### 1. `participant_llm` is not fully aligned with the cleanest FAP story

The local participants support the project's strongest claim:

- local work happens inside the participant
- only governed output leaves the boundary

`participant_llm` does not fully fit that model because raw input is transmitted to an external
provider before governance is applied to the response. That limitation is honestly documented, but
it means the protocol now has two different execution shapes:

- local governed participants
- outbound LLM-backed participant

This is not fatal, but it must be modeled explicitly.

### 2. Discovery is still descriptive, not operational

The runtime now exposes canonical `/profile` and `/status` endpoints for all current participants,
including `participant_llm`.

That is real progress, but the coordinator still does not use that metadata for first-class
routing decisions. Until routing consumes discovery, profile/status will remain only partly
realized.

### 3. The project can still be misread as "connectors + orchestrator"

Without stronger use cases and routing, people may still read the current runtime as:

- docs connector
- kb connector
- logs connector
- optional llm connector

instead of as the beginning of a protocol for federated domain runtimes.

## What Was Weak In Earlier Release Framing

The earliest alpha framing had several limitations:

- participants felt like fixed adapters, not domain runtimes
- the future architecture line was under-specified
- the use-case story was weaker than the protocol story
- deployment and contributor ergonomics were less mature

The project is now in a better place because contributors expanded both:

- expressiveness of participants
- usability of the local runtime

## What Should Stay

These should remain stable pillars of FAP:

- typed canonical messages
- protocol-first coordination
- local execution as the default participant model
- governed export
- participant-originated aggregation
- durable run and event state
- evidence-linked final outputs
- coordinator-managed federation as the default topology

## What Should Be Replaced Or Upgraded

The project should move from:

- participants as fixed connectors

to:

- participants as self-describing domain runtimes

It should also move from:

- static routing

to:

- routing from participant discovery + task constraints

And from:

- one generic source reference model

to:

- typed evidence/provenance categories

## Strategic Recommendation

The current alpha is already strong enough to keep building from. The right next step is not to
chase generic "MAS" features. The right next step is to make the protocol more useful for real
domain agents while preserving its strongest boundary:

- FAP between participants
- MCP inside participants

That is the direction that best fits the project's identity.

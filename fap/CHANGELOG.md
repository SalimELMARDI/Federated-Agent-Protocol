# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog, with the first public alpha captured below.

## [Unreleased]

- No unreleased changes documented yet.

## [0.1.0-alpha] - 2026-03-25

### Added

- typed protocol core in `fap_core`
- version-aware dispatch over `(protocol, version, message_type)`
- DB-first coordinator runtime with durable `protocol_events` and `run_snapshots`
- three real reference participants:
  - `participant_docs`
  - `participant_kb`
  - `participant_logs`
- participant-originated `fap.aggregate.submit`
- `summary_merge` aggregation
- source-level evidence refs carried through task completion, aggregate submission, and aggregate result payloads
- thin `/ask` wrapper
- `fap_client` Python integration layer
- `fap_mcp` MCP bridge
- release demo scenario and integration examples

### Changed

- promoted the database layer from durable shadow persistence to the primary coordinator runtime state source
- tightened selected runtime/protocol vocabularies to enums while preserving wire compatibility
- added trusted participant identity consistency validation to coordinator dispatch and orchestration
- upgraded docs, kb, and logs participants to local file-backed connectors

### Notes

- This is an alpha reference release.
- The runtime is working end to end but is not yet production stable.
- Trust is currently coordinator-side identity consistency validation, not cryptographic authentication.

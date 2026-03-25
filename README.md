# Federated Agent Protocol

This git repository contains the FAP monorepo in the [fap/](./fap) directory.

FAP is a governed federated protocol for coordinating work across private domains without centralizing raw private data. The current codebase is prepared for a first public alpha release as:

- a protocol alpha
- a reference runtime
- a developer preview
- not yet production stable

## Where The Actual Project Lives

The active Python monorepo, packages, apps, docs, specs, and examples are all under:

- [fap/](./fap)

That directory contains:

- `fap_core`
- `fap_client`
- `fap_mcp`
- the DB-first coordinator reference runtime
- the `participant_docs`, `participant_kb`, and `participant_logs` reference participants
- the demo scenario
- the protocol spec
- release notes and checklist

## Start Here

If you want to understand or run the project, begin with:

- [fap/README.md](./fap/README.md)

Useful follow-on docs:

- protocol spec: [fap/spec/README.md](./fap/spec/README.md)
- demo scenario: [fap/examples/demo_scenario/README.md](./fap/examples/demo_scenario/README.md)
- Python client example: [fap/examples/agent_integration/README.md](./fap/examples/agent_integration/README.md)
- MCP example: [fap/examples/mcp_integration/README.md](./fap/examples/mcp_integration/README.md)
- alpha release note draft: [fap/docs/release-notes/v0.1.0-alpha.md](./fap/docs/release-notes/v0.1.0-alpha.md)

## Repo Note

The repository root is the git root. The Python/project root for the actual FAP monorepo is `fap/`.

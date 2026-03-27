# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Layout

This is a Python monorepo. All substantive code lives under `fap/`. The git root contains only a brief README and this file.

```
fap/
├── packages/
│   ├── fap_core/      # Protocol SDK: typed messages, codec, registry, version-aware dispatch, policy engine, identity
│   ├── fap_client/    # Thin Python client for /ask, run inspection, event inspection
│   └── fap_mcp/       # MCP bridge exposing fap_client as Model Context Protocol tools
├── apps/
│   ├── coordinator_api/    # DB-first coordinator: dispatch, orchestration, aggregation, durable state
│   ├── participant_docs/   # Reference participant: local document search with governed export
│   ├── participant_kb/     # Reference participant: local KB search with governed export
│   ├── participant_logs/   # Reference participant: local log search with governed export
│   └── participant_llm/    # LLM-backed participant: sends query to LLM, returns governed response
├── spec/              # Protocol specification (Markdown)
├── examples/          # Demo scenario, agent integration, MCP integration, sample data
├── migrations/        # Alembic DB migrations
└── tests/             # Root-level integration tests
```

## Development Commands

All commands run from `fap/` with the virtual environment activated.

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"   # installs all packages + pytest, ruff, mypy

# Run all checks (lint + type check + tests)
make verify

# Individual checks
python -m pytest                         # all tests
python -m pytest path/to/test_file.py   # single test file
python -m ruff check .                  # lint
python -m mypy apps packages tests      # type check

# Demo — 3-participant (original, no LLM)
make demo-coordinator   # coordinator on :8011
make demo-docs          # docs participant on :8012
make demo-kb            # kb participant on :8013
make demo-logs          # logs participant on :8014
make demo-run           # run end-to-end demo scenario

# Demo — 4-participant (with LLM)
make demo-coordinator-llm  # coordinator with LLM support on :8011
make demo-docs             # :8012
make demo-kb               # :8013
make demo-logs             # :8014
make demo-llm              # LLM participant on :8015 (set LLM_API_KEY first)
make demo-run
```

## Architecture

### Protocol Flow

FAP coordinates federated tasks across isolated participant domains without moving raw data:

1. **Task Create** — user/agent sends `fap.task.create` to the coordinator
2. **Dispatch** — coordinator dispatches to registered participants for evaluation
3. **Evaluation** — participants reply `fap.task.accept` or `fap.task.reject`
4. **Execution** — accepted participants search local data and apply the shared policy engine
5. **Completion** — participants return `fap.task.complete` with policy-governed exports and source evidence refs
6. **Attestation** — participants send `fap.policy.attest` confirming policy application
7. **Aggregation** — participants send `fap.aggregate.submit`; coordinator produces `fap.aggregate.result`

Raw data never leaves participant boundaries; only approved exports are transmitted.

### Key Design Patterns

**Protocol-first:** All messages are defined in `fap_core` as Pydantic v2 models. Version-aware dispatch keys on `(protocol, version, message_type)`. The canonical JSON codec lives in `fap_core/codec.py`.

**Governed execution:** Each participant runs the same deterministic policy engine before exporting results. Policy attestation is attached to every submission.

**Provenance:** Every message carries `task_id`, `run_id`, `trace_id`. Source evidence refs (`participant_id`, `source_id`, `source_title`, `source_path`) are attached to results.

**DB-first state:** The coordinator persists all events to a `protocol_events` table and maintains `run_snapshots`. Alembic manages schema migrations.

### Package Responsibilities

- **`fap_core`** — pure protocol: message types, enums, codec, identity helpers, policy engine. No I/O.
- **`fap_client`** — HTTP client wrapping coordinator endpoints; returns typed `AskResponse`, `RunSnapshot`, `RunEvents`.
- **`fap_mcp`** — exposes `fap_ask`, `fap_get_run`, `fap_get_events`, `fap_submit_message` as MCP tools.
- **`coordinator_api`** — FastAPI app with routes for `/ask`, dispatch, orchestration, aggregation, run/message inspection. Business logic split across `service/` (orchestration, aggregation, dispatch, persistence, state, store) and `db/` (SQLAlchemy models, session).
- **Participant apps** — identical structure: `/api/` (route handlers), `/service/` (business logic), `/adapters/` (local data access). Each runs as an independent FastAPI service.

## Tech Stack

Python 3.12+, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy, Alembic, httpx (async), MCP. Default database is SQLite; PostgreSQL supported via `DATABASE_URL`.

## Configuration

Copy `fap/.env.example` to `fap/.env` before running services:

- `DATABASE_URL` — SQLAlchemy URL (defaults to SQLite)
- `FAP_COORDINATOR_URL` — coordinator base URL (used by participants and client)
- `PARTICIPANT_DOCS_PATH`, `PARTICIPANT_KB_PATH`, `PARTICIPANT_LOGS_PATH` — local data directories

`participant_llm` specific (no `.env.example` entry, set in shell):

- `LLM_PROVIDER` — `anthropic` (default) | `openai` | `ollama`
- `LLM_MODEL` — model name, defaults to `claude-sonnet-4-20250514`
- `LLM_API_KEY` — API key for Anthropic or OpenAI
- `LLM_BASE_URL` — override base URL for OpenAI-compatible or Ollama endpoints

## Alpha Limitations

The current v0.1.0-alpha has no cryptographic authentication, no event sourcing, no advanced aggregation strategies, and no production hardening. The trust model relies on a coordinator-side registry with identity consistency validation only.

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

### LLM Participant Governance Model

**`participant_llm` has a different trust model than file-backed participants:**

File-backed participants (`docs`, `kb`, `logs`):
1. Search local data
2. Apply policy engine to results
3. Export only governed data
4. **Raw data never leaves the boundary**

LLM-backed participant (`participant_llm`):
1. Receive raw `input_query` from coordinator
2. **Send query to external LLM API (UNGOVERNED)** ⚠️
3. Receive LLM response
4. Apply policy engine to response
5. Export governed response

**Governance gap:** Input queries are transmitted to external LLM providers (Anthropic, OpenAI, Ollama) before governance. Only responses are governed.

**Security implications:**
- Queries may contain PII, PHI, credentials, or proprietary data
- External transmission may violate data locality requirements (GDPR, HIPAA)
- Requires explicit opt-in via `PARTICIPANT_LLM_ENABLE=true`
- Service refuses to start without acknowledgment

**Design decision (PR feedback #1 — @SalimELMARDI):**
Rather than silently sending ungoverned data to external APIs, we require explicit operator acknowledgment through environment variable, startup warning logs, and comprehensive documentation. This makes the trust model transparent and prevents accidental deployment in environments where ungoverned external transmission would violate policy.

**Design decision (PR feedback #2 — @SalimELMARDI):**
The LLM participant rejects empty capability requests and requests without at least one `llm.*` capability. This prevents automatic participation in all queries by default. Callers must explicitly request `llm.query`, `llm.summarize`, or `llm.reason` to include the LLM participant in orchestration. This ensures that only queries intentionally meant for external LLM transmission will be sent to the LLM provider.

**Design decision (PR feedback #3 — @SalimELMARDI):**
The coordinator's `/ask` endpoint implements capability-based dispatch filtering. When no `llm.*` capability is present in `requested_capabilities`, the coordinator skips dispatching to the LLM participant entirely (passes `None` for LLM URLs to orchestration). This provides defense-in-depth: coordinator-side filtering prevents unnecessary network calls, and participant-side rejection (feedback #2) provides redundant safety if coordinator filtering is bypassed. Only requests with explicit `llm.*` capabilities trigger LLM dispatch.

**Design decision (PR feedback #4 — @SalimELMARDI):**
When the LLM provider call fails (network error, auth failure, rate limit), the participant returns HTTP 503 (Service Unavailable) instead of converting the failure to a successful `fap.task.complete` message with an error string. This makes failures protocol-visible to the coordinator. Before this change, failures were silently converted to success strings like `"LLM query failed: ..."` which leaked provider error messages into aggregates and made it impossible to distinguish failures from valid results. Now, the coordinator can detect execution failures and skip the LLM contribution, resulting in clean aggregates with only successful participant results.

**Design decision (PR feedback #7 — @SalimELMARDI):**
The LLM HTTP client uses async/await throughout (`httpx.AsyncClient`) instead of blocking I/O (`httpx.Client`). The entire call chain from API handler through executor to HTTP client is async. This prevents blocking the FastAPI event loop during LLM API calls, allowing concurrent request processing. Before this change, blocking HTTP calls could severely degrade performance under load as each LLM request would block the entire event loop.

**Future enhancement:** Add input query governance to apply policy before external transmission (redaction, rejection, configurable modes).

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

- `PARTICIPANT_LLM_ENABLE` — **REQUIRED.** Set to `true` to acknowledge trust model and enable service
- `LLM_PROVIDER` — `anthropic` (default) | `openai` | `ollama`
- `LLM_MODEL` — model name, defaults to `claude-sonnet-4-20250514`
- `LLM_API_KEY` — API key for Anthropic or OpenAI
- `LLM_BASE_URL` — override base URL for OpenAI-compatible or Ollama endpoints

**Trust Model Note:** `participant_llm` differs from file-backed participants in governance model. Input queries are sent to external LLM APIs **before** governance is applied (only responses are governed). This requires explicit opt-in via `PARTICIPANT_LLM_ENABLE=true`. See `fap/apps/participant_llm/README.md` § Trust Model for details.

## Alpha Limitations

The current v0.1.0-alpha has no cryptographic authentication, no event sourcing, no advanced aggregation strategies, and no production hardening. The trust model relies on a coordinator-side registry with identity consistency validation only.

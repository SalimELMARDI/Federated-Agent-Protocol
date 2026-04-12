# Feature: participant_llm — LLM-backed FAP Participant

This folder contains the validation test suite for the `participant_llm` feature. It is intended to accompany the PR and provide reviewers with a clear picture of what was added and how it was verified.

## What This Feature Adds

`participant_llm` is a fourth FAP participant that answers the coordinator's query using a language model instead of a local file-backed dataset. It follows the exact same participant contract as `participant_docs`, `participant_kb`, and `participant_logs`.

**New code:**
- `fap/apps/participant_llm/` — full participant app (config, LLM adapter, evaluator, executor, FastAPI routes)
- `fap/packages/fap_core/src/fap_core/identity.py` — `ParticipantId.PARTICIPANT_LLM` and its trusted identity entry
- `fap/apps/coordinator_api/` — optional LLM participant wiring in dispatch, orchestration, agent, main, and orchestrate/ask API handlers
- `fap/Makefile` — `make demo-llm` and `make demo-coordinator-llm` targets
- `fap/examples/demo_scenario/README.md` — extended demo instructions

**Design decisions:**
- All `participant_llm_*` parameters are `str | None = None` throughout the coordinator call chain — the LLM step is skipped entirely when URLs are absent, so all existing 3-participant tests pass unchanged.
- The LLM adapter catches `LLMCallError` and returns a graceful error summary with empty `source_refs` rather than raising — the orchestration run continues and the coordinator still produces a valid (partial) aggregate.
- Timing instrumentation (`time.perf_counter()`) is added around each evaluate/execute dispatch step, logged at INFO level via Python `logging` — no schema changes.
- **Trust model acknowledgment (PR feedback #1):** `participant_llm` sends input queries to external LLM providers BEFORE governance (only responses are governed). This differs from FAP's core "policy before export" principle. To prevent silent ungoverned transmission, the service requires explicit opt-in via `PARTICIPANT_LLM_ENABLE=true` and logs startup warnings. See `fap/apps/participant_llm/README.md` § Trust Model for full details.
- **Explicit capability requirement (PR feedback #2):** The LLM participant rejects empty capability requests and requests without at least one `llm.*` capability (`llm.query`, `llm.summarize`, `llm.reason`). This prevents automatic participation in all queries by default, ensuring only explicitly LLM-intended queries are sent to external providers.
- **Coordinator-side dispatch filtering (PR feedback #3):** The coordinator's `/ask` endpoint checks for `llm.*` capabilities before dispatching. If no `llm.*` capability is present, the coordinator passes `None` for LLM URLs to orchestration, preventing any network call to the LLM participant. This provides defense-in-depth alongside participant-side rejection (feedback #2).

## Test Files

| File | What it tests |
|---|---|
| `test_unit_evaluator.py` | Capability negotiation: accept/reject paths, envelope correlation |
| `test_unit_executor.py` | Execution bundle: policy paths, source refs, error graceful degradation, provenance chain |
| `test_integration_orchestration.py` | 4-participant orchestration with monkeypatched LLM: ordering, participant_count, aggregate content |
| `test_protocol_compliance.py` | FAP protocol invariants: envelope routing, message-type strings, identity registration, cross-message consistency |

## Running the Tests

From the `fap/` directory with the virtualenv activated:

```cmd
python -m pytest test-feature-llm-participant/ -v
```

To run the full suite including all existing tests:

```cmd
python -m pytest
```

All tests should pass with no real LLM API calls — the LLM adapter is monkeypatched with a deterministic stub wherever network calls would otherwise occur.

## LLM Configuration (for the live demo only)

| Env var | Default | Description |
|---|---|---|
| `PARTICIPANT_LLM_ENABLE` | _(unset)_ | **REQUIRED.** Set to `true` to acknowledge trust model |
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `openai`, or `ollama` |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Model passed to the API |
| `LLM_API_KEY` | _(empty)_ | Required for Anthropic / OpenAI |
| `LLM_BASE_URL` | _(provider default)_ | Override for OpenAI-compatible endpoints |

For Ollama (no API key needed):
```cmd
export PARTICIPANT_LLM_ENABLE=true  # Required acknowledgment
export LLM_PROVIDER=ollama
export LLM_MODEL=llama3.2
make demo-llm
```

**Note:** `PARTICIPANT_LLM_ENABLE=true` is required for the service to start. Without it, the service exits with a trust model warning.

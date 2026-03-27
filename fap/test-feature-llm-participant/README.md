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
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `openai`, or `ollama` |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Model passed to the API |
| `LLM_API_KEY` | _(empty)_ | Required for Anthropic / OpenAI |
| `LLM_BASE_URL` | _(provider default)_ | Override for OpenAI-compatible endpoints |

For Ollama (no API key needed):
```cmd
set LLM_PROVIDER=ollama
set LLM_MODEL=llama3.2
make demo-llm
```

# Agent Integration Example

This example shows how an external Python program can treat FAP as a capability through the new `fap_client` package.

The goal is not to expose every internal coordinator endpoint. Instead, the client gives an outside agent a simple entrypoint for:

- asking a federated question through `/ask`
- inspecting the resulting run through `GET /runs/{run_id}`
- inspecting persisted events through `GET /runs/{run_id}/events`

## What This Example Demonstrates

- user question in
- `FAPClient.ask(...)`
- final answer back out
- follow-up inspection of the run snapshot
- follow-up inspection of persisted event types

No LLM calls are used here. This is a thin neutral adapter layer that another Python agent can call.

## Prerequisites

From the repo root:

```cmd
cd fap
call .venv\Scripts\activate.bat
python -m pip install -e .
```

Start the coordinator and participants using the same local setup as the release demo:

- coordinator on `http://127.0.0.1:8011`
- `participant_docs` on `http://127.0.0.1:8012`
- `participant_kb` on `http://127.0.0.1:8013`
- `participant_logs` on `http://127.0.0.1:8014`

## Run The Example

```cmd
python examples\agent_integration\simple_agent.py --coordinator-url http://127.0.0.1:8011 privacy
```

You can also omit the question and use the default:

```cmd
python examples\agent_integration\simple_agent.py --coordinator-url http://127.0.0.1:8011
```

## Expected Output

The example prints a compact agent-style summary:

- run id
- final answer
- accepted participants from the run snapshot
- persisted event types in order

For the default `privacy` question, the final answer should include:

```text
[participant_docs] [SUMMARY ONLY] Matched docs: Privacy Policy Memo
[participant_kb] [SUMMARY ONLY] Matched KB entries: Privacy controls
[participant_logs] [SUMMARY ONLY] Matched log events: privacy-monitor
```

## Files

- `packages/fap_client/src/fap_client/client.py`
- `packages/fap_client/src/fap_client/models.py`
- `examples/agent_integration/simple_agent.py`

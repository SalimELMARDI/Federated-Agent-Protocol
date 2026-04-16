# FAP v0.1 Alpha Demo Scenario

This demo shows a complete local FAP run from `fap.task.create` through governed execution, participant-originated `fap.aggregate.submit`, and final `fap.aggregate.result`.

## What This Demo Covers
- canonical `fap.task.create` entering the coordinator
- one-shot orchestration across:
  - `participant_docs`
  - `participant_kb`
  - `participant_logs`
- governed execution with policy-constrained exports
- participant-originated `fap.aggregate.submit`
- final `fap.aggregate.result`
- persisted coordinator run snapshot and ordered event inspection

An extended variant (`demo-coordinator-llm`) also includes `participant_llm`, which answers the query using a real LLM and contributes its governed response to the same aggregate result.

## Prerequisites
- Python 3.12
- the repo virtualenv activated
- editable install from the `fap/` repo root:

```cmd
cd fap
call .venv\Scripts\activate.bat
python -m pip install -e .
```

## Start The Services
Open four terminals from the `fap/` repo root.

Terminal 1:
```cmd
make demo-coordinator
```

Terminal 2:
```cmd
make demo-docs
```

Terminal 3:
```cmd
make demo-kb
```

Terminal 4:
```cmd
make demo-logs
```

If you do not use `make`, the exact commands are defined in [Makefile](../../Makefile).

## Run The Demo
From a fifth terminal:

```cmd
make demo-run
```

This runs [run_demo.py](./run_demo.py), which:
- loads [create_task.json](./create_task.json)
- refreshes the envelope IDs and timestamp so the demo is re-runnable
- posts the task to the coordinator
- triggers one-shot orchestration
- fetches the final run snapshot
- fetches the persisted event list
- prints a compact summary

## What Success Looks Like
- the create call returns `202 accepted`
- orchestration returns `200` with a canonical `fap.aggregate.result`
- all three participants evaluate and execute successfully
- the final merged answer includes:
  - `participant_docs`
  - `participant_kb`
  - `participant_logs`
- persisted events appear in protocol order and include:
  - `fap.task.create`
  - `fap.task.accept`
  - `fap.task.complete`
  - `fap.policy.attest`
  - `fap.aggregate.submit`
  - `fap.aggregate.result`

## Inspect After The Demo
- input example: [create_task.json](./create_task.json)
- expected runtime flow: [expected_flow.md](./expected_flow.md)
- run snapshot endpoint:
  - `GET http://127.0.0.1:8011/runs/{run_id}`
- persisted events endpoint:
  - `GET http://127.0.0.1:8011/runs/{run_id}/events`

## Demo Scenario
The demo task asks the system to review local privacy-related material across documents, knowledge-base entries, and operational logs. It uses `input_query="privacy"` because that query deterministically matches all three local participant datasets.

## Demo With participant_llm

To add the LLM participant to the demo, open five terminals instead of four:

```cmd
make demo-coordinator-llm   # Terminal 1 — coordinator with LLM participant enabled
make demo-docs              # Terminal 2
make demo-kb                # Terminal 3
make demo-logs              # Terminal 4
make demo-llm               # Terminal 5 — LLM participant on :8015
make demo-run               # Terminal 6
```

Set `LLM_API_KEY` (and optionally `LLM_PROVIDER`, `LLM_MODEL`) before starting Terminal 5.
For local models via Ollama: `set LLM_PROVIDER=ollama` and `set LLM_MODEL=llama3.2` — no API key needed.

The aggregate result will include contributions from all four participants.

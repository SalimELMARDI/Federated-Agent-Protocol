# participant_llm

LLM-backed FAP participant. Sends the coordinator's query to a language model and returns the governed response as a canonical FAP execution bundle.

## Config

| Env var | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | Provider: `anthropic`, `openai`, or `ollama` |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Model name passed to the API |
| `LLM_API_KEY` | _(empty)_ | API key for Anthropic or OpenAI |
| `LLM_BASE_URL` | _(provider default)_ | Override base URL for OpenAI-compatible endpoints |

Provider URL defaults:
- `anthropic` → `https://api.anthropic.com/v1/messages`
- `openai` → `https://api.openai.com/v1`
- `ollama` → `http://localhost:11434/v1`

## Capabilities

`llm.query`, `llm.summarize`, `llm.reason`

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check (includes configured provider and model) |
| `POST` | `/messages` | FAP message ingress — parse and ACK |
| `POST` | `/evaluate` | Evaluate `fap.task.create` → accept/reject |
| `POST` | `/execute` | Execute `fap.task.create` → governed LLM response bundle |

## Source Refs

The participant returns one `SourceRef` per response:
- `source_id` — model name (e.g. `claude-sonnet-4-20250514`)
- `source_title` — `LLM: {model}`
- `source_path` — API endpoint URL

## Start

```cmd
python -m uvicorn participant_llm.main:app --host 127.0.0.1 --port 8015
```

Or with make (from `fap/`):

```cmd
make demo-llm
```

## Demo With LLM

Start all five services then run with the LLM-enabled coordinator:

```cmd
make demo-coordinator-llm   # Terminal 1 — coordinator with LLM support on :8011
make demo-docs              # Terminal 2
make demo-kb                # Terminal 3
make demo-logs              # Terminal 4
make demo-llm               # Terminal 5 — LLM participant on :8015
make demo-run               # Terminal 6 — run demo
```

Set `LLM_API_KEY` before starting `demo-llm` when using Anthropic or OpenAI.

## Local Models (Ollama)

```cmd
set LLM_PROVIDER=ollama
set LLM_MODEL=llama3.2
make demo-llm
```

No API key needed for Ollama.

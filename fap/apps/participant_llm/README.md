# participant_llm

LLM-backed FAP participant. It sends the coordinator's query to a language model and returns the
governed response as a canonical FAP execution bundle.

## Trust Model

This participant differs from the file-backed participants (`participant_docs`, `participant_kb`,
`participant_logs`) in one important way:

- the raw `input_query` is transmitted to an external or local-model API before governance is
  applied to the returned content

The current flow is:

1. receive the raw `input_query` from the coordinator
2. send the query to the configured LLM provider
3. receive the model response
4. apply the shared FAP policy engine to the response
5. return the governed response bundle to the coordinator

That means `participant_llm` should be understood as an **outbound participant**, not a local
participant.

### Enable When

- queries are known to be non-sensitive
- the provider is trusted and compliant with your policies
- external transmission is acceptable for the task

### Do Not Enable When

- queries may contain PII, PHI, credentials, financial data, or trade secrets
- data locality or zero-trust policy forbids ungoverned external transmission

### Explicit Opt-In Required

Set:

```bash
export PARTICIPANT_LLM_ENABLE=true
```

Without that environment variable, the service refuses to start.

## Execution Failures

When the provider call fails, the participant returns **HTTP 503** instead of a fake successful
`fap.task.complete`. This keeps failures protocol-visible to the coordinator.

Typical failure cases:

- network or timeout errors
- missing or invalid API keys
- provider rate limits or 5xx responses
- malformed provider responses

## Discovery Metadata

`participant_llm` now exposes canonical discovery metadata just like the other participants:

- `GET /profile`
- `GET /status`

The advertised execution posture is:

- `execution_class = outbound`
- `outbound_network_access = true`
- `supports_mcp = false`
- `supports_followup = false`

This makes the trust posture visible at the protocol surface instead of hiding it in prose only.

## Config

| Env var | Default | Description |
| --- | --- | --- |
| `PARTICIPANT_LLM_ENABLE` | _(unset)_ | Required. Set to `true` to acknowledge the trust model and enable the service |
| `LLM_PROVIDER` | `anthropic` | Provider: `anthropic`, `openai`, or `ollama` |
| `LLM_MODEL` | `claude-sonnet-4-20250514` | Model name passed to the API |
| `LLM_API_KEY` | _(empty)_ | API key for Anthropic or OpenAI |
| `LLM_BASE_URL` | _(provider default)_ | Override base URL for OpenAI-compatible endpoints |

Provider URL defaults:

- `anthropic` -> `https://api.anthropic.com/v1/messages`
- `openai` -> `https://api.openai.com/v1`
- `ollama` -> `http://localhost:11434/v1`

## Capabilities

- `llm.query`
- `llm.summarize`
- `llm.reason`

Security constraint:

- this participant only accepts requests that explicitly include at least one `llm.*` capability
- empty capability requests are rejected
- mixed capability requests are filtered so the participant only claims the `llm.*` capabilities it
  actually supports

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check with provider/model metadata |
| `GET` | `/profile` | Canonical participant profile |
| `GET` | `/status` | Canonical participant status |
| `POST` | `/messages` | FAP message ingress: parse and acknowledge |
| `POST` | `/evaluate` | Evaluate `fap.task.create` and accept/reject |
| `POST` | `/execute` | Execute `fap.task.create` and return governed output bundle |

## Source Refs

The participant currently returns one `SourceRef` per response:

- `source_id` -> model name
- `source_title` -> `LLM: {model}`
- `source_path` -> provider endpoint URL

This is provider provenance, not local evidence in the same sense as docs, KB, or logs.

## Start

```cmd
python -m uvicorn participant_llm.main:app --host 127.0.0.1 --port 8015
```

Or with `make` from `fap/`:

```cmd
make demo-llm
```

## Demo With LLM

Start all five services, then run the LLM-enabled coordinator:

```cmd
export PARTICIPANT_LLM_ENABLE=true
export LLM_API_KEY=your_api_key_here

make demo-coordinator-llm
make demo-docs
make demo-kb
make demo-logs
make demo-llm
make demo-run
```

The LLM participant is only used for requests with explicit `llm.*` capabilities.

## Local Models (Ollama)

```cmd
export PARTICIPANT_LLM_ENABLE=true
export LLM_PROVIDER=ollama
export LLM_MODEL=llama3.2
make demo-llm
```

No API key is needed for Ollama, but the trust-model acknowledgment is still required.

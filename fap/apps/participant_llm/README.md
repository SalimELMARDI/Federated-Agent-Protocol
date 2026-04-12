# participant_llm

LLM-backed FAP participant. Sends the coordinator's query to a language model and returns the governed response as a canonical FAP execution bundle.

---

## ⚠️ Trust Model

**IMPORTANT:** This participant differs from file-backed participants (`participant_docs`, `participant_kb`, `participant_logs`) in its governance model.

### Governance Limitation

**Input queries are transmitted to external LLM providers BEFORE governance is applied.**

Unlike file-backed participants where raw data never leaves the boundary, `participant_llm`:
1. Receives raw `input_query` from coordinator
2. **Sends query to external LLM API (UNGOVERNED)** ⚠️
3. Receives LLM response
4. Applies FAP policy engine to response (GOVERNED) ✓
5. Returns governed response to coordinator

### Security Implications

- **Raw user queries** may contain sensitive data:
  - Personally Identifiable Information (PII)
  - Protected Health Information (PHI)
  - Financial data, credentials, API keys
  - Proprietary business information
  - Trade secrets
  
- **External transmission risk**: Queries are sent to third-party LLM providers (Anthropic, OpenAI) or local Ollama instances before any governance checks.

- **Compliance considerations**: May violate data locality requirements (GDPR, HIPAA, SOC2, etc.) if queries contain regulated data.

### Safe Usage Guidelines

✓ **Enable `participant_llm` when:**
- Queries are known to be non-sensitive (general knowledge questions)
- External LLM provider is trusted and compliant with your policies
- Your organization's privacy/compliance requirements allow external transmission
- You have explicit authorization to send data to the chosen LLM provider

❌ **DO NOT enable when:**
- Queries may contain PII, PHI, financial data, or trade secrets
- Compliance requires data to remain within specific geographic boundaries
- Zero-trust security policy prohibits ungoverned external transmission
- You cannot guarantee query content will be non-sensitive

### Explicit Opt-In Required

To acknowledge this trust model and enable the service, set:

```bash
export PARTICIPANT_LLM_ENABLE=true
```

**Without this environment variable, the service will refuse to start.**

The startup logs will display a warning confirming governance limitations.

### Future Work

A future enhancement may add **input query governance** to apply policy before external transmission. This would enable:
- Redaction of sensitive patterns before sending to LLM
- Rejection of queries containing ungovernable sensitive data
- Configurable governance modes (PARANOID, REDACT, PASSTHROUGH)

See tracking issue: [Add input query governance](#) _(link TBD)_

---

## Execution Failures

When the LLM provider call fails (network error, auth failure, rate limit, etc.), the participant returns **HTTP 503 (Service Unavailable)** instead of a successful `fap.task.complete` message with an error string. This makes failures protocol-visible to the coordinator.

### Failure Scenarios

- **Network errors:** Connection timeout, DNS failure, proxy error
- **Auth errors:** Invalid API key, expired token, missing credentials
- **Provider errors:** Rate limit exceeded, service unavailable (5xx), quota exceeded
- **Validation errors:** Malformed response from LLM API

### Coordinator Behavior

When participant_llm returns HTTP 503:
1. Coordinator logs execution failure for `participant_llm`
2. Skips LLM contribution to aggregate result
3. Other participants (docs, kb, logs) continue normally
4. Final aggregate contains only successful participants

### Benefits

✓ **Protocol-visible failures** — Coordinator knows execution failed (not success with error string)  
✓ **No error leakage** — Provider error messages don't leak into user-facing aggregates  
✓ **Clean aggregates** — Only valid results included, no "LLM query failed: ..." strings  
✓ **Accurate metrics** — Success/failure counts reflect reality  

### Example

```bash
# Invalid API key
export LLM_API_KEY=invalid_key_xyz
make demo-llm

# Query with llm.query capability
curl http://localhost:8011/ask -d '{
  "query": "privacy policy",
  "requested_capabilities": ["llm.query"]
}'

# Result: 3 participants (docs, kb, logs)
# LLM execution failed with HTTP 503, coordinator skipped it
```

### Future Enhancement

Add retry logic with exponential backoff for transient failures (network errors, rate limits).

---

## Config

| Env var | Default | Description |
|---|---|---|
| `PARTICIPANT_LLM_ENABLE` | _(unset)_ | **REQUIRED.** Set to `true` to acknowledge trust model and enable service |
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

**Security Constraint:** This participant **requires explicit `llm.*` capabilities** in the task request. Empty capability requests or requests without at least one `llm.*` capability will be rejected. This prevents automatic participation in queries not intended for external LLM transmission.

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
# Set required environment variables first
export PARTICIPANT_LLM_ENABLE=true        # Acknowledge trust model
export LLM_API_KEY=your_api_key_here     # For Anthropic or OpenAI

# Start services
make demo-coordinator-llm   # Terminal 1 — coordinator with LLM support on :8011
make demo-docs              # Terminal 2
make demo-kb                # Terminal 3
make demo-logs              # Terminal 4
make demo-llm               # Terminal 5 — LLM participant on :8015
make demo-run               # Terminal 6 — run demo
```

**Note:** `PARTICIPANT_LLM_ENABLE=true` is required. The service will refuse to start without it.

## Local Models (Ollama)

```cmd
export PARTICIPANT_LLM_ENABLE=true  # Required acknowledgment
export LLM_PROVIDER=ollama
export LLM_MODEL=llama3.2
make demo-llm
```

No API key needed for Ollama, but `PARTICIPANT_LLM_ENABLE=true` is still required (queries are still sent to an external process, even if local).

# MCP Integration Example

This example shows how to expose the FAP coordinator runtime as a small MCP server built on top of the existing `fap_client` package.

The MCP wrapper is intentionally thin:

- `fap_ask`
- `fap_get_run`
- `fap_get_events`
- `fap_submit_message`

It does not talk to participants directly and it does not reimplement coordinator HTTP logic. All tool behavior flows through `fap_client`.

## Prerequisites

From the repo root:

```cmd
cd fap
call .venv\Scripts\activate.bat
python -m pip install -e .
```

Start the existing coordinator and participants first. The default local runtime is:

- coordinator: `http://127.0.0.1:8011`
- `participant_docs`: `http://127.0.0.1:8012`
- `participant_kb`: `http://127.0.0.1:8013`
- `participant_logs`: `http://127.0.0.1:8014`

## Run The MCP Server

Default `stdio` transport:

```cmd
python examples\mcp_integration\run_server.py --coordinator-url http://127.0.0.1:8011
```

Optional streamable HTTP transport:

```cmd
python examples\mcp_integration\run_server.py --transport streamable-http --host 127.0.0.1 --port 8015
```

## Exposed Tools

- `fap_ask(question: str)`
- `fap_get_run(run_id: str)`
- `fap_get_events(run_id: str)`
- `fap_submit_message(message: dict)`

## Environment

You can also set:

```cmd
set FAP_COORDINATOR_URL=http://127.0.0.1:8011
```

If `--coordinator-url` is not provided, the server uses `FAP_COORDINATOR_URL` and then falls back to `http://127.0.0.1:8011`.

## Files

- `packages/fap_mcp/src/fap_mcp/server.py`
- `packages/fap_mcp/src/fap_mcp/tools.py`
- `examples/mcp_integration/run_server.py`

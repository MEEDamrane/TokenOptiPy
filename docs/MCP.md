# TokenOptiPy MCP server

TokenOptiPy exposes its local static-analysis engine through the Model Context Protocol using the standard `stdio` transport.

## Start manually

```bash
python -m tokenoptipy.mcp_server
```

or:

```bash
tokenoptipy-mcp
```

## Tools

| Tool | Purpose |
|---|---|
| `inspect_workspace` | Build an in-memory TokenGraph and return statistics, hotspots, and findings. |
| `analyze_prompt_file` | Analyze one workspace file without returning its prompt body. |
| `validate_prompt_change` | Compare original and candidate prompts and enforce safety invariants. |
| `query_token_flow` | Search prompts, context, files, functions, and model calls in the graph. |
| `get_traceability` | Return recent safe execution metadata. |

All tools are declared read-only and do not modify source files.

## Environment

| Variable | Meaning |
|---|---|
| `TOKENOPTIPY_WORKSPACE_ROOT` | Absolute workspace boundary. Tool paths cannot escape it. |
| `TOKENOPTIPY_TRACE_FILE` | JSONL trace path. Defaults to `.tokenoptipy/trace.jsonl`. |
| `PYTHONUTF8` | Recommended value: `1`. |
| `PYTHONUNBUFFERED` | Recommended value: `1` for `stdio`. |

## Trace schema

Each call writes a `started` event and a terminal `completed` or `error` event:

```json
{
  "schema_version": 1,
  "timestamp": "2026-07-31T10:20:30.123Z",
  "trace_id": "e0ad...",
  "tool": "inspect_workspace",
  "status": "completed",
  "duration_ms": 182,
  "summary": "Scanned 42 nodes; 3 findings; 1200 static prompt tokens"
}
```

The trace deliberately excludes:

- prompt bodies;
- tool arguments;
- query text;
- API keys and credentials;
- source-code excerpts.

## Codex

The VS Code extension maintains a managed section in the trusted workspace file `.codex/config.toml`. Restart the Codex session after the first installation or after changing the Python executable.

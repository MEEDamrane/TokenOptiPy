# Implemented architecture

```text
Codex / VS Code agent
        │ MCP stdio
        ▼
python -m tokenoptipy.mcp_server
        │
        ├── inspect_workspace
        ├── analyze_prompt_file
        ├── validate_prompt_change
        ├── query_token_flow
        └── get_traceability
        │
        ▼
.tokenoptipy/trace.jsonl
        │ watched by VS Code
        ▼
One status-bar item
```

## Visible VS Code UI

Only the TokenOptiPy status-bar item is created. It shows:

- latest MCP tool;
- started/completed/error state;
- execution duration;
- trace identifier;
- safe summary.

It does not create an Activity Bar icon, sidebar, webview, diagnostics collection, Problems entries, Quick Pick, context menu, output channel, or notification.

## Security boundaries

- every MCP tool is read-only;
- file paths must stay under `TOKENOPTIPY_WORKSPACE_ROOT`;
- the trace excludes prompt bodies, arguments, queries, source excerpts, and secrets;
- source code is never modified by the MCP server;
- the status bar reads local JSONL only.

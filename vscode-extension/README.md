# TokenOptiPy MCP Traceability for VS Code

This extension has one visible UI element: a status-bar item that shows TokenOptiPy MCP tool traceability.

It does not add a sidebar, diagnostics panel, graph view, context menus, Quick Picks, or notifications.

## Behavior

- Registers `python -m tokenoptipy.mcp_server` as a local `stdio` MCP server in VS Code.
- Maintains a TokenOptiPy block in `.codex/config.toml` so Codex can discover the same server.
- Watches `.tokenoptipy/trace.jsonl`.
- Shows the latest tool name, execution state, duration, and trace identifier in the status bar.
- Opens the local JSONL trace when the bar is selected.

The trace never stores prompt bodies, secrets, or tool arguments.

## Tools

- `inspect_workspace`
- `analyze_prompt_file`
- `validate_prompt_change`
- `query_token_flow`
- `get_traceability`

All tools are read-only and restricted to the configured workspace.

## Requirements

- VS Code 1.105 or newer.
- Python 3.10 or newer.
- TokenOptiPy installed in the configured Python interpreter:

```bash
pip install -e .
```

After installation or an extension update, reload VS Code and start a new Codex session so MCP configuration is rediscovered.

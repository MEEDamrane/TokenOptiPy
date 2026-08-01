from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CLIENT_PATHS = {
    "claude": ".mcp.json",
    "claude-desktop": ".claude/claude_desktop_config.json",
    "vscode": ".vscode/mcp.json",
    "cursor": ".cursor/mcp.json",
    "windsurf": ".windsurf/mcp.json",
    "cline": ".cline/mcp.json",
    "roo": ".roo/mcp.json",
    "continue": ".continue/mcp.json",
    "generic": "tokenoptipy-mcp.json",
}
MANAGED_BEGIN = "# BEGIN TOKENOPTIPY (managed)"
MANAGED_END = "# END TOKENOPTIPY (managed)"


def _server(root: Path, python: str) -> dict[str, Any]:
    return {
        "type": "stdio",
        "command": python,
        "args": ["-m", "tokenoptipy.mcp_server"],
        "cwd": str(root),
        "env": {
            "TOKENOPTIPY_WORKSPACE_ROOT": str(root),
            "TOKENOPTIPY_TRACE_FILE": str(root / ".tokenoptipy" / "trace.jsonl"),
            "PYTHONUTF8": "1",
            "PYTHONUNBUFFERED": "1",
        },
    }


def write_mcp_configs(
    root: str | Path,
    *,
    clients: list[str] | None = None,
    python: str = "python",
) -> list[Path]:
    workspace = Path(root).expanduser().resolve()
    selected = clients or ["codex", *CLIENT_PATHS]
    unknown = sorted(set(selected) - {"codex", *CLIENT_PATHS})
    if unknown:
        raise ValueError(f"Unsupported MCP client(s): {', '.join(unknown)}")
    server = _server(workspace, python)
    written: list[Path] = []
    for client in selected:
        if client == "codex":
            path = workspace / ".codex" / "config.toml"
            env_values = ", ".join(
                f"{key} = {json.dumps(value)}" for key, value in server["env"].items()
            )
            block = (
                f"{MANAGED_BEGIN}\n"
                "[mcp_servers.tokenoptipy]\n"
                f"command = {json.dumps(python)}\n"
                'args = ["-m", "tokenoptipy.mcp_server"]\n'
                f"cwd = {json.dumps(str(workspace))}\n"
                "startup_timeout_sec = 20\n"
                "tool_timeout_sec = 120\n"
                f"env = {{ {env_values} }}\n"
                f"{MANAGED_END}"
            )
            existing = path.read_text(encoding="utf-8") if path.exists() else ""
            start, end = existing.find(MANAGED_BEGIN), existing.find(MANAGED_END)
            if start >= 0 and end >= start:
                content = existing[:start] + block + existing[end + len(MANAGED_END) :]
            else:
                content = existing.rstrip() + ("\n\n" if existing.strip() else "") + block + "\n"
        else:
            path = workspace / CLIENT_PATHS[client]
            key = "servers" if client == "vscode" else "mcpServers"
            existing_data: dict[str, Any] = {}
            if path.exists():
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise ValueError(f"MCP config must contain a JSON object: {path}")
                existing_data = loaded
            servers = existing_data.setdefault(key, {})
            if not isinstance(servers, dict):
                raise ValueError(f"MCP config field '{key}' must be an object: {path}")
            servers["tokenoptipy"] = server
            content = json.dumps(existing_data, indent=2, ensure_ascii=False) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


AGENT_PATHS = {
    "codex": "AGENTS.md",
    "claude": "CLAUDE.md",
    "copilot": ".github/copilot-instructions.md",
    "cursor": ".cursor/rules/tokenoptipy.mdc",
    "windsurf": ".windsurf/rules/tokenoptipy.md",
    "cline": ".clinerules/tokenoptipy.md",
    "roo": ".roo/rules/tokenoptipy.md",
    "continue": ".continue/rules/tokenoptipy.md",
}

AGENT_INSTRUCTIONS = """# TokenOptiPy

Before changing prompts, context assembly, or model calls, use the TokenOptiPy MCP tools
`inspect_workspace` and `get_prompt_flow`. After a change, use `validate_prompt_change` and
`build_graph_report`. Never include complete prompt bodies, credentials, secrets, or sensitive
tool arguments in traces, logs, findings, commits, or chat output. Keep all analysis local.
"""


def write_agent_instructions(root: str | Path, *, clients: list[str] | None = None) -> list[Path]:
    workspace = Path(root).expanduser().resolve()
    selected = clients or list(AGENT_PATHS)
    unknown = sorted(set(selected) - set(AGENT_PATHS))
    if unknown:
        raise ValueError(f"Unsupported agent client(s): {', '.join(unknown)}")
    written = []
    for client in selected:
        path = workspace / AGENT_PATHS[client]
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        block = f"{MANAGED_BEGIN}\n{AGENT_INSTRUCTIONS.rstrip()}\n{MANAGED_END}"
        start, end = existing.find(MANAGED_BEGIN), existing.find(MANAGED_END)
        if start >= 0 and end >= start:
            content = existing[:start] + block + existing[end + len(MANAGED_END) :]
        else:
            content = existing.rstrip() + ("\n\n" if existing.strip() else "") + block + "\n"
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written

from __future__ import annotations

import json
from pathlib import Path

from tokenoptipy.cli import main
from tokenoptipy.graph_engine import prompt_flow
from tokenoptipy.graph_models import GraphEdge, GraphFinding, GraphNode, TokenGraph
from tokenoptipy.graph_reporting import graph_html
from tokenoptipy.mcp_tools import build_graph_report, get_prompt_flow


def sample_graph(tmp_path: Path) -> TokenGraph:
    prompt = GraphNode("prompt:one", "prompt", "System prompt", "app.py", 2, static_tokens=12)
    context = GraphNode("context:user", "context", "user", "app.py", 3, static_tokens=4)
    call = GraphNode("call:one", "model_call", "client.chat", "app.py", 4)
    graph = TokenGraph(str(tmp_path), nodes={item.id: item for item in (prompt, context, call)})
    graph.add_edge(GraphEdge(context.id, prompt.id, "INCLUDES"))
    graph.add_edge(GraphEdge(prompt.id, call.id, "FLOWS_TO", {"role": "system"}))
    graph.add_finding(GraphFinding("LARGE_PROMPT", "warning", prompt.id, "Large", "Shorten"))
    return graph


def test_prompt_flow_has_required_traceability_fields(tmp_path: Path) -> None:
    result = prompt_flow(sample_graph(tmp_path), "prompt:one")
    assert result["node_id"] == "prompt:one"
    assert result["prompt_tokens"] == 12
    assert result["connected_node_tokens"] == {"call:one": 0, "context:user": 4}
    assert result["total_flow_tokens"] == 16
    assert result["model_calls"][0]["id"] == "call:one"
    assert result["model_call_paths"][0]["relations"] == ["FLOWS_TO"]
    assert result["findings"][0]["code"] == "LARGE_PROMPT"


def test_v030_cli_generates_universal_configs_and_agent_files(tmp_path: Path) -> None:
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"existing": {"command": "safe"}}}), encoding="utf-8"
    )
    (tmp_path / "AGENTS.md").write_text("# Existing instructions\n", encoding="utf-8")
    assert main(["mcp-config", str(tmp_path), "--client", "all", "--python", "python3"]) == 0
    assert main(["agent-init", str(tmp_path), "--client", "all"]) == 0
    assert (tmp_path / ".codex" / "config.toml").exists()
    assert (tmp_path / ".mcp.json").exists()
    assert (tmp_path / ".vscode" / "mcp.json").exists()
    assert (tmp_path / ".cursor" / "mcp.json").exists()
    assert (tmp_path / ".windsurf" / "mcp.json").exists()
    assert (tmp_path / ".cline" / "mcp.json").exists()
    assert (tmp_path / ".roo" / "mcp.json").exists()
    assert (tmp_path / ".continue" / "mcp.json").exists()
    assert (tmp_path / "tokenoptipy-mcp.json").exists()
    assert (tmp_path / "AGENTS.md").exists()
    config = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert config["mcpServers"]["tokenoptipy"]["command"] == "python3"
    assert config["mcpServers"]["existing"]["command"] == "safe"
    assert "Existing instructions" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")


def test_mcp_flow_and_report_return_trace_ids(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "prompt.txt").write_text("You are concise. Return JSON only.", encoding="utf-8")
    monkeypatch.setenv("TOKENOPTIPY_WORKSPACE_ROOT", str(tmp_path))
    report = build_graph_report()
    assert report["outputs"]
    graph = json.loads(
        (tmp_path / "tokenoptipy-out" / "graph.json").read_text(encoding="utf-8")
    )
    prompt_id = next(node["id"] for node in graph["nodes"] if node["type"] == "prompt")
    result = get_prompt_flow(prompt_id)
    assert result["trace_id"]
    assert "prompt body" in result["privacy"]
    assert (tmp_path / "tokenoptipy-out" / "graph.html").exists()


def test_html_is_self_contained_safe_and_interactive(tmp_path: Path) -> None:
    graph = sample_graph(tmp_path)
    graph.nodes["prompt:one"] = GraphNode("prompt:one", "prompt", "</script><img onerror=x>")
    output = graph_html(graph)
    assert "<script src=" not in output and "<link " not in output
    assert "</script><img" not in output
    assert "marker-end" in output and "Light / dark" in output
    assert "edgeFilter" in output and "Connected nodes" in output and "Trace ID" in output

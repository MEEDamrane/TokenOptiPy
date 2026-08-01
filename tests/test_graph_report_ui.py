from __future__ import annotations

import json
from pathlib import Path

from tokenoptipy.graph_models import GraphEdge, GraphNode, TokenGraph
from tokenoptipy.graph_reporting import graph_html


def graph(root: Path) -> TokenGraph:
    value = TokenGraph(str(root))
    value.add_node(GraphNode("prompt:one", "prompt", "Prompt", static_tokens=932))
    value.add_node(GraphNode("variable:one", "variable", "Value"))
    value.add_node(GraphNode("function:one", "function", "send"))
    value.add_node(GraphNode("call:one", "model_call", "client.responses.create"))
    value.add_edge(GraphEdge("prompt:one", "variable:one", "USES_VARIABLE"))
    value.add_edge(GraphEdge("variable:one", "function:one", "FLOWS_TO"))
    value.add_edge(GraphEdge("function:one", "call:one", "CALLS_MODEL"))
    return value


def write_trace(root: Path, event: dict[str, object]) -> None:
    directory = root / ".tokenoptipy"
    directory.mkdir()
    (directory / "trace.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")


def test_complete_trace_uses_real_fields(tmp_path: Path) -> None:
    write_trace(tmp_path, {"trace_id": "abc123", "tool": "inspect_workspace", "status": "completed", "timestamp": "2026-08-01T12:42:18Z", "duration_ms": 84, "summary": "Workspace inspected"})
    output = graph_html(graph(tmp_path), "tokenoptipy-out/graph.html")
    assert all(value in output for value in ("abc123", "2026-08-01T12:42:18Z", "completed", '"duration_ms": 84', "tokenoptipy-out/graph.html"))
    assert "MCP trace log" not in output
    assert "static prompt tokens" in output
    assert "formatTraceTimestamp" in output
    assert "formatDuration" in output


def test_missing_and_invalid_trace_values_have_safe_fallbacks(tmp_path: Path) -> None:
    write_trace(tmp_path, {"trace_id": "bad", "timestamp": "not-a-date", "status": "completed"})
    output = graph_html(graph(tmp_path))
    assert "Invalid Date" not in output
    assert "Not available" in output
    assert "No report generated" in output


def test_report_without_trace_has_empty_state(tmp_path: Path) -> None:
    output = graph_html(graph(tmp_path))
    assert "No MCP trace available." in output
    assert "Run TokenOptiPy through a configured MCP client" in output


def test_unused_uses_directed_reachability_and_accessible_tabs(tmp_path: Path) -> None:
    output = graph_html(graph(tmp_path))
    assert "function reachesModel(id)" in output
    assert "edge.source===current" in output
    assert "visited=new Set" in output
    assert "aria-selected" in output
    assert "aria-label','Close inspector panel" in output

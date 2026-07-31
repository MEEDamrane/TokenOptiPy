from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path

from tokenoptipy.trace import read_trace_events, trace_tool


def test_trace_contains_only_safe_metadata(tmp_path: Path, monkeypatch) -> None:
    trace_path = tmp_path / ".tokenoptipy" / "trace.jsonl"
    monkeypatch.setenv("TOKENOPTIPY_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("TOKENOPTIPY_TRACE_FILE", str(trace_path))
    secret_prompt = "api_key=sk-this-must-never-appear"

    with trace_tool("analyze_prompt_file", root=tmp_path) as trace:
        trace.set_summary("Analyzed prompts/system.txt; 42 tokens; 1 finding")
        _ = secret_prompt

    events = read_trace_events(limit=10, root=tmp_path)
    assert [event["status"] for event in events] == ["started", "completed"]
    raw = trace_path.read_text(encoding="utf-8")
    assert secret_prompt not in raw
    assert "analyze_prompt_file" in raw
    assert events[-1]["duration_ms"] >= 0


def test_trace_error_is_recorded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TOKENOPTIPY_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("TOKENOPTIPY_TRACE_FILE", str(tmp_path / "trace.jsonl"))

    with suppress(ValueError), trace_tool("inspect_workspace", root=tmp_path):
        raise ValueError("private argument value")

    event = read_trace_events(limit=1, root=tmp_path)[0]
    assert event["status"] == "error"
    assert event["summary"] == "ValueError"
    assert "private argument value" not in json.dumps(event)

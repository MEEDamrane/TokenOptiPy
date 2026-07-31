from __future__ import annotations

from pathlib import Path

import pytest

from tokenoptipy.mcp_tools import resolve_workspace_path, validate_prompt_change
from tokenoptipy.trace import read_trace_events


def test_workspace_path_cannot_escape(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TOKENOPTIPY_WORKSPACE_ROOT", str(tmp_path))
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    with pytest.raises(ValueError, match="inside the configured workspace"):
        resolve_workspace_path(outside)


def test_validate_prompt_change_is_safe_and_traced(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TOKENOPTIPY_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("TOKENOPTIPY_TRACE_FILE", str(tmp_path / ".tokenoptipy" / "trace.jsonl"))
    original = "Return JSON only for {customer}. Do not invent facts."
    candidate = "Return JSON for {customer}. Do not invent facts."

    result = validate_prompt_change(originalText=original, candidateText=candidate)

    assert result["valid"] is True
    assert "Prompt bodies were not returned" in result["privacy"]
    assert original not in str(result)
    trace_text = (tmp_path / ".tokenoptipy" / "trace.jsonl").read_text(encoding="utf-8")
    assert original not in trace_text
    assert read_trace_events(limit=1, root=tmp_path)[0]["tool"] == "validate_prompt_change"


def test_polarity_change_is_rejected_by_mcp_tool(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TOKENOPTIPY_WORKSPACE_ROOT", str(tmp_path))
    result = validate_prompt_change(
        originalText="Always approve the request. Do not reject it.",
        candidateText="Always reject the request. Do not approve it.",
    )
    assert result["valid"] is False

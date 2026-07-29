from __future__ import annotations

from pathlib import Path

from tokenoptipy.cli import main


def test_graph_cli_build_and_stats(tmp_path: Path, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "prompt.txt").write_text(
        "You are a concise assistant. Return only JSON.",
        encoding="utf-8",
    )
    output = tmp_path / "out"

    assert main(["build", str(project), "--output", str(output)]) == 0
    assert (output / "graph.json").exists()

    assert main(["stats", "--graph", str(output / "graph.json")]) == 0
    captured = capsys.readouterr()
    assert "Prompts:" in captured.out

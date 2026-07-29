from pathlib import Path

from tokenoptipy.cli import main


def test_count_command(tmp_path: Path, capsys) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Hello world", encoding="utf-8")
    assert main(["count", str(prompt), "--backend", "simple"]) == 0
    assert "tokens" in capsys.readouterr().out

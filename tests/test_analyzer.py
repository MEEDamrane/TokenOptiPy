from tokenoptipy.analyzer import analyze_prompt


def test_duplicate_line_detection() -> None:
    prompt = "Classify the text.\nClassify the text.\nReturn JSON."
    codes = {finding.code for finding in analyze_prompt(prompt)}
    assert "TOK002" in codes


def test_json_detection() -> None:
    prompt = '{\n  "task": "classify",\n  "label": "support"\n}'
    codes = {finding.code for finding in analyze_prompt(prompt)}
    assert "TOK006" in codes

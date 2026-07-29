from tokenoptipy.optimizer import optimize_prompt
from tokenoptipy.validators import ValidationPolicy, validate_candidate


def test_optimizer_reduces_duplicate_lines() -> None:
    prompt = "Classify this message.\nClassify this message.\nReturn only the label."
    report = optimize_prompt(prompt, backend="simple")
    assert report.selected_count.tokens < report.original_count.tokens
    assert "Classify this message." in report.selected_prompt


def test_placeholder_preservation() -> None:
    result = validate_candidate(
        "Reply to {customer_name} in 30 words.",
        "Reply in 30 words.",
    )
    assert not result.valid
    assert "{customer_name}" in result.missing_placeholders


def test_required_term_policy() -> None:
    policy = ValidationPolicy(required_terms=("JSON",))
    result = validate_candidate("Return JSON only.", "Return only.", policy)
    assert not result.valid


def test_compact_json_preserves_keys() -> None:
    prompt = '{\n  "task": "classify",\n  "label": "support"\n}'
    report = optimize_prompt(prompt, backend="simple")
    assert report.selected_candidate in {"compact-json", "combined-safe"}
    assert '"task"' in report.selected_prompt

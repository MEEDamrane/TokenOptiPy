from tokenoptipy.graph_models import GraphEdge, TokenGraph
from tokenoptipy.privacy import redact_preview
from tokenoptipy.transformations import normalize_whitespace
from tokenoptipy.validators import validate_candidate


def test_modern_secrets_are_redacted() -> None:
    values = (
        "".join(
            (
                "github",
                "_pat_",
                "abcdefghijklmnopqrstuvwxyz1234567890",
            )
        ),
        "".join(
            (
                "AI",
                "za",
                "abcdefghijklmnopqrstuvwxyz1234567890",
            )
        ),
        "".join(
            (
                "sk",
                "_live_",
                "abcdefghijklmnopqrstuvwxyz",
            )
        ),
    )

    for value in values:
        preview, detected = redact_preview(f"token={value}")
        assert detected is True
        assert value not in preview

def test_yaml_indentation_is_preserved() -> None:
    prompt = "headers:\n  Authorization: Bearer value\n  Accept: application/json\n"
    assert normalize_whitespace(prompt) == prompt.rstrip("\n")


def test_yaml_structure_change_is_rejected() -> None:
    original = "headers:\n  Authorization: Bearer value\n  Accept: application/json"
    candidate = "headers:\nAuthorization: Bearer value\nAccept: application/json"
    result = validate_candidate(original, candidate)
    assert result.valid is False
    assert "indentation-sensitive structure changed" in result.notes


def test_instruction_polarity_change_is_rejected() -> None:
    result = validate_candidate(
        "Always approve the request. Do not reject it.",
        "Always reject the request. Do not approve it.",
    )
    assert result.valid is False
    assert any("polarity change" in note for note in result.notes)


def test_duplicate_edges_remain_unique() -> None:
    graph = TokenGraph(project_root=".")
    edge = GraphEdge("a", "b", "FLOWS_TO")
    for _ in range(10_000):
        graph.add_edge(edge)
    assert graph.edges == [edge]

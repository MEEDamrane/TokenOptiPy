from __future__ import annotations

import json
from pathlib import Path

from tokenoptipy.graph_engine import (
    build_token_graph,
    graph_hotspots,
    query_graph,
    shortest_path,
)
from tokenoptipy.graph_reporting import write_graph_outputs


def create_project(root: Path) -> Path:
    (root / "prompts").mkdir(parents=True)
    (root / "prompts" / "system.txt").write_text(
        "You are a support assistant. Return only JSON with intent and confidence.",
        encoding="utf-8",
    )
    (root / "app.py").write_text(
        '''SYSTEM_PROMPT = """You are a support assistant.\nReturn only JSON.\n"""\n\ndef classify(client, history):\n    return client.chat.completions.create(prompt=SYSTEM_PROMPT, messages=history)\n''',
        encoding="utf-8",
    )
    return root


def test_build_graph_finds_prompts_and_model_calls(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project")
    graph = build_token_graph(project)

    node_types = {node.type for node in graph.nodes.values()}
    edge_types = {edge.type for edge in graph.edges}

    assert "prompt" in node_types
    assert "model_call" in node_types
    assert "FLOWS_TO" in edge_types
    assert any(finding.code == "TG005" for finding in graph.findings)


def test_graph_reports_are_created(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project")
    graph = build_token_graph(project)
    outputs = write_graph_outputs(graph, tmp_path / "out")

    assert outputs["json"].exists()
    assert outputs["markdown"].exists()
    assert outputs["html"].exists()
    payload = json.loads(outputs["json"].read_text(encoding="utf-8"))
    assert payload["nodes"]
    assert "TokenOptiPy TokenGraph" in outputs["html"].read_text(encoding="utf-8")


def test_hotspots_query_and_path(tmp_path: Path) -> None:
    project = create_project(tmp_path / "project")
    graph = build_token_graph(project)

    hotspots = graph_hotspots(graph)
    assert hotspots
    assert hotspots[0]["static_tokens"] >= 0

    matches = query_graph(graph, "support prompt")
    assert matches

    prompt = next(node for node in graph.nodes.values() if node.type == "prompt")
    file_node = graph.nodes[f"file:{prompt.path}"]
    path = shortest_path(graph, file_node.id, prompt.id)
    assert len(path) == 2


def test_python_prompt_secrets_are_redacted_from_all_reports(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    secret = "sk-this-is-a-sensitive-test-key"
    (project / "app.py").write_text(
        f'API_PROMPT = "You are an assistant. api_key=\\"{secret}\\" Return only JSON."\n',
        encoding="utf-8",
    )

    graph = build_token_graph(project)
    prompt = next(node for node in graph.nodes.values() if node.type == "prompt")
    assert prompt.attributes["has_possible_secret"] is True
    assert prompt.attributes["preview"] == (
        "You are an assistant. [REDACTED_SECRET] Return only JSON."
    )
    assert any(finding.code == "SEC001" for finding in graph.findings)

    outputs = write_graph_outputs(graph, tmp_path / "out")
    assert secret not in outputs["json"].read_text(encoding="utf-8")
    assert secret not in outputs["html"].read_text(encoding="utf-8")


def test_inline_prompt_secret_is_redacted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    secret = "ghp_abcdefghijklmnopqrstuvwxyz123456"
    (project / "app.py").write_text(
        "def run(llm):\n"
        f'    return llm.invoke(prompt="Use token {secret} and return JSON")\n',
        encoding="utf-8",
    )

    graph = build_token_graph(project)
    prompt = next(node for node in graph.nodes.values() if node.type == "prompt")
    assert secret not in str(prompt.attributes["preview"])
    assert prompt.attributes["has_possible_secret"] is True


def test_json_schema_values_are_not_prompts(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "schema.json").write_text(
        json.dumps(
            {
                "system_instruction": "Return a JSON object with intent and confidence.",
                "schema": {
                    "intent": "billing",
                    "confidence": "number",
                    "reply": "string",
                },
            }
        ),
        encoding="utf-8",
    )

    graph = build_token_graph(project)
    labels = {node.label for node in graph.nodes.values() if node.type == "prompt"}
    assert labels == {"schema.json:$.system_instruction"}


def test_json_chat_message_content_is_a_prompt(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "messages.json").write_text(
        json.dumps({"messages": [{"role": "system", "content": "Answer concisely."}]}),
        encoding="utf-8",
    )

    graph = build_token_graph(project)
    prompts = [node for node in graph.nodes.values() if node.type == "prompt"]
    assert len(prompts) == 1
    assert prompts[0].attributes["json_path"] == "$.messages[0].content"


def test_html_report_escapes_script_terminators(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    payload = "</script><script>globalThis.compromised = true</script>"
    (project / "prompt.txt").write_text(payload, encoding="utf-8")

    graph = build_token_graph(project)
    html = write_graph_outputs(graph, tmp_path / "out")["html"].read_text(encoding="utf-8")
    assert payload not in html
    assert "\\u003c/script\\u003e" in html


def test_ordinary_markdown_and_yaml_are_not_prompts(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text(
        "# Installation\n\nRun the package manager and then start the application.",
        encoding="utf-8",
    )
    (project / "settings.yaml").write_text(
        "database:\n  host: localhost\n  port: 5432\n",
        encoding="utf-8",
    )

    graph = build_token_graph(project)
    assert not [node for node in graph.nodes.values() if node.type == "prompt"]


def test_yaml_with_prompt_key_is_detected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "llm.yaml").write_text(
        "system_prompt: |\n  Answer concisely and return JSON.\nmodel: local\n",
        encoding="utf-8",
    )

    graph = build_token_graph(project)
    prompts = [node for node in graph.nodes.values() if node.type == "prompt"]
    assert len(prompts) == 1
    assert prompts[0].label == "llm.yaml"

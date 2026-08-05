from __future__ import annotations

import json
from pathlib import Path

from tokenoptipy.graph_engine import build_token_graph, compute_stats, load_graph, prompt_flow


def write(root: Path, name: str, value: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def classified(graph, classification: str):
    return [node for node in graph.nodes.values() if node.attributes.get("classification") == classification]


def test_non_llm_javascript_strings_are_not_prompts(tmp_path: Path) -> None:
    write(tmp_path, "package.json", json.dumps({"name": "demo", "description": "A useful editor extension"}))
    write(tmp_path, "main.js", 'console.log("diagnostic ready"); vscode.window.showErrorMessage("Operation failed");')
    graph = build_token_graph(tmp_path)
    assert classified(graph, "config_text")
    assert classified(graph, "log_message")
    assert classified(graph, "error_message")
    assert not classified(graph, "llm_prompt")
    assert compute_stats(graph)["false_positives_avoided"] >= 3
    candidate = next(node for node in graph.nodes.values() if node.type in {"prompt", "string"})
    flow = prompt_flow(graph, candidate.id) if candidate.type == "prompt" else None
    if flow:
        assert flow["mode"] == "Candidate Prompt Flow"


def test_real_python_and_javascript_model_flows(tmp_path: Path) -> None:
    write(tmp_path, "app.py", 'from openai import OpenAI\nprompt = "Summarize: " + user_text\nresponse = OpenAI().responses.create(input=prompt)\n')
    write(tmp_path, "ollama.ts", 'import ollama from "ollama"; const messages = [{role:"user",content:`Explain ${topic}`}]; ollama.chat({messages});')
    write(tmp_path, "chain.py", 'from langchain_openai import ChatOpenAI\nprompt = f"Answer {question}"\nresult = ChatOpenAI().invoke(prompt)\n')
    graph = build_token_graph(tmp_path)
    assert len(classified(graph, "llm_prompt")) >= 3
    assert {"PROMPT_TO_MODEL_CALL"} <= {edge.type for edge in graph.edges}
    assert {node.label for node in graph.nodes.values() if node.type == "model_call"} >= {"OpenAI().responses.create", "ollama.chat", "ChatOpenAI().invoke"}


def test_multiple_providers_stats_and_legacy_graph(tmp_path: Path) -> None:
    write(tmp_path, "main.ts", 'import OpenAI from "openai"; import ollama from "ollama"; const prompt="Answer"; OpenAI.responses.create({input:prompt}); ollama.generate({prompt});')
    graph = build_token_graph(tmp_path)
    stats = compute_stats(graph)
    assert stats["llm_prompt_count"] == 1
    assert len(stats["detected_model_calls"]) == 2
    legacy = tmp_path / "old.json"
    legacy.write_text(json.dumps({"project_root": ".", "nodes": [{"id":"prompt:old","type":"prompt","label":"old","attributes":{}}], "edges":[], "findings":[]}), encoding="utf-8")
    assert load_graph(legacy).nodes["prompt:old"].label == "old"

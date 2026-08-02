from __future__ import annotations

import json
from pathlib import Path

import pytest

from tokenoptipy.graph_engine import build_token_graph, prompt_flow


def write(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    ("extension", "call"),
    [
        ("js", "openai.responses.create"),
        ("js", "openai.chat.completions.create"),
        ("ts", "anthropic.messages.create"),
        ("ts", "model.generateContent"),
        ("ts", "generateText"),
        ("ts", "model.invoke"),
        ("js", "ollama.chat"),
    ],
)
def test_prompt_and_model_calls(tmp_path: Path, extension: str, call: str) -> None:
    write(tmp_path, f"main.{extension}", f'const systemPrompt = `Summarize: ${{document}}`; {call}({{ prompt: systemPrompt }});')
    graph = build_token_graph(tmp_path)
    assert any(node.label == "systemPrompt" for node in graph.nodes.values())
    assert any(node.type == "model_call" and node.label == call for node in graph.nodes.values())
    assert {"javascript" if extension == "js" else "typescript"} <= set(graph.metadata["detected_languages"])


def test_messages_fs_imports_and_exclusions(tmp_path: Path) -> None:
    write(tmp_path, "package.json", "{}")
    write(tmp_path, "prompt.ts", 'export const SYSTEM_PROMPT = "You are a concise assistant";')
    write(tmp_path, "main.ts", 'import { SYSTEM_PROMPT } from "./prompt"; const messages = [{role:"system", content:SYSTEM_PROMPT}, {role:"user", content:userMessage}]; openai.responses.create({input: messages});')
    write(tmp_path, "load.cjs", 'const prompt = fs.readFileSync("./system.prompt", "utf8"); ollama.chat({prompt});')
    write(tmp_path, "system.prompt", "Return only the final answer.")
    write(tmp_path, "node_modules/bad.js", 'const prompt = "must not appear";')
    write(tmp_path, "dist/bad.js", 'const prompt = "must not appear";')
    write(tmp_path, "app.min.js", 'const prompt = "must not appear";')
    write(tmp_path, "package-lock.json", json.dumps({"prompt": "must not appear"}))
    graph = build_token_graph(tmp_path)
    paths = {node.path for node in graph.nodes.values()}
    assert not any(path and ("node_modules" in path or "dist/" in path or path.endswith(".min.js")) for path in paths)
    assert not any(node.path == "package-lock.json" and node.type == "prompt" for node in graph.nodes.values())
    assert any(edge.type == "IMPORTS" and edge.target == "file:prompt.ts" for edge in graph.edges)
    assert any(node.attributes.get("loaded_path") == "./system.prompt" for node in graph.nodes.values())


def test_tsx_ui_is_not_prompt_but_used_prompt_is(tmp_path: Path) -> None:
    write(tmp_path, "view.tsx", 'export const View = () => <button>Save changes</button>; const systemPrompt = `You are helpful`; model.generateContent({contents: systemPrompt});')
    graph = build_token_graph(tmp_path)
    prompts = [node for node in graph.nodes.values() if node.type == "prompt"]
    assert [node.label for node in prompts] == ["systemPrompt"]


def test_config_and_determinism(tmp_path: Path) -> None:
    write(tmp_path, "tokenoptipy.config.json", json.dumps({"languages": ["typescript"], "exclude": ["custom"]}))
    write(tmp_path, "main.ts", 'const prompt = "Summarize this document"; openai.responses.create({input:prompt});')
    write(tmp_path, "custom/skip.ts", 'const prompt = "skip";')
    left, right = build_token_graph(tmp_path), build_token_graph(tmp_path)
    assert left.to_dict() == right.to_dict()
    assert not any(node.path == "custom/skip.ts" for node in left.nodes.values())
    flow = prompt_flow(left, "prompt")
    assert flow["model_calls"]


def test_invalid_config_is_clear(tmp_path: Path) -> None:
    write(tmp_path, "tokenoptipy.config.json", '{"languages":["ruby"]}')
    with pytest.raises(ValueError, match="unsupported language"):
        build_token_graph(tmp_path)

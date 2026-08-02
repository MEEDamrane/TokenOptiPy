from __future__ import annotations

import json
from pathlib import Path

import pytest

from tokenoptipy.cli import main
from tokenoptipy.graph_engine import build_token_graph
from tokenoptipy.languages import LANGUAGE_REGISTRY
from tokenoptipy.mcp_tools import get_language_support

SOURCES = {
    "php": ("app.php", "$systemPrompt = <<<PROMPT\nYou are a PHP assistant.\nPROMPT;\n$openai->chat(messages: $systemPrompt);"),
    "java": ("App.java", 'import com.openai.Client; class App { static final String SYSTEM_PROMPT = """\nYou are a Java assistant.\n"""; void run(){ client.generate(SYSTEM_PROMPT, "model"); }}'),
    "c": ("app.c", '#include "local.h"\nstatic const char *SYSTEM_PROMPT = "You are a C assistant. " "Return only JSON."; void run(){ openai_chat(SYSTEM_PROMPT, "model"); }'),
    "cpp": ("app.cpp", 'constexpr auto SYSTEM_PROMPT = R"P(You are a C++ assistant.)P"; void run(){ llama.generate(SYSTEM_PROMPT, "model"); }'),
    "csharp": ("App.cs", 'using Azure.AI.OpenAI; class App { const string SystemPrompt = """You are a C# assistant."""; void Run(){ client.CompleteChatAsync(messages: SystemPrompt); }}'),
    "go": ("app.go", 'package main\nimport "github.com/openai/openai-go"\nconst systemPrompt = `You are a Go assistant.`\nfunc run(){ client.CreateChatCompletion(messages, systemPrompt) }'),
    "rust": ("app.rs", 'use async_openai::Client; const SYSTEM_PROMPT: &str = r#"You are a Rust assistant."#; fn run(){ client.chat(SYSTEM_PROMPT, "model"); }'),
}


@pytest.mark.parametrize("language", SOURCES)
def test_multilingual_prompt_and_model_call(tmp_path: Path, language: str) -> None:
    filename, source = SOURCES[language]
    (tmp_path / filename).write_text(source, encoding="utf-8")
    graph = build_token_graph(tmp_path, language=language)
    assert any(node.type == "prompt" and node.attributes["language"] == language for node in graph.nodes.values())
    assert any(node.type == "model_call" for node in graph.nodes.values())


def test_registry_cli_and_mcp_language_support(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "main.go").write_text("package main", encoding="utf-8")
    assert set(SOURCES) <= set(LANGUAGE_REGISTRY.language_ids)
    assert main(["languages", str(tmp_path), "--json"]) == 0
    assert any(item["language"] == "go" for item in json.loads(capsys.readouterr().out))
    monkeypatch.setenv("TOKENOPTIPY_WORKSPACE", str(tmp_path))
    support = get_language_support(".")
    assert "go" in support["detected_languages"]


def test_repeated_language_selection_and_false_create(tmp_path: Path) -> None:
    (tmp_path / "a.php").write_text("$prompt = 'You are helpful.'; $db->create($prompt);", encoding="utf-8")
    (tmp_path / "A.java").write_text('class A { String prompt = "You are helpful."; }', encoding="utf-8")
    graph = build_token_graph(tmp_path, language=["php", "java"])
    assert {"php", "java"} <= set(graph.metadata["detected_languages"])
    assert not any(node.type == "model_call" for node in graph.nodes.values())

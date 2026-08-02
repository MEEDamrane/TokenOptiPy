from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelCallSignature:
    language: str
    sdk_terms: tuple[str, ...]
    methods: tuple[str, ...]
    argument_keys: tuple[str, ...] = ("prompt", "messages", "input", "model")
    confidence: float = 0.9


SIGNATURES = (
    ModelCallSignature("php", ("openai", "anthropic", "gemini", "ollama"), ("chat", "create", "responses", "completions", "messages")),
    ModelCallSignature("java", ("openai", "azure.ai.openai", "spring.ai", "langchain4j", "gemini", "anthropic"), ("create", "generateContent", "call", "invoke", "generate", "prompt")),
    ModelCallSignature("c", ("openai", "llama", "ollama", "azure"), ("chat", "completion", "generate", "invoke")),
    ModelCallSignature("cpp", ("openai", "llama", "ollama", "azure"), ("chat", "completion", "generate", "invoke")),
    ModelCallSignature("csharp", ("OpenAI", "Azure.AI.OpenAI", "SemanticKernel", "Microsoft.Extensions.AI", "Anthropic", "Ollama"), ("CompleteChatAsync", "GetChatMessageContentAsync", "InvokePromptAsync", "InvokeAsync", "GenerateAsync", "CreateResponseAsync", "ChatAsync")),
    ModelCallSignature("go", ("openai", "anthropic", "genai", "langchaingo", "ollama"), ("CreateChatCompletion", "GenerateContent", "Generate", "Chat", "Invoke")),
    ModelCallSignature("rust", ("async_openai", "anthropic", "gemini", "ollama", "rig", "mistral", "llama"), ("create", "chat", "generate", "completion", "invoke")),
)

from __future__ import annotations

LLM_ENDPOINT_TERMS = ("openai", "anthropic", "generativelanguage", "ollama", "/v1/chat", "/v1/responses", "/v1/completions")


def has_llm_http_evidence(source: str) -> bool:
    lowered = source.lower()
    endpoint = any(term in lowered for term in LLM_ENDPOINT_TERMS)
    payload = any(key in lowered for key in ('"model"', '"messages"', '"prompt"', '"input"'))
    return endpoint and payload

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

from .graph_models import GraphEdge, GraphNode, TokenGraph

STRING_CLASSES = (
    "llm_prompt", "candidate_prompt", "developer_message", "error_message",
    "log_message", "ui_text", "config_text", "documentation", "unknown_string",
)

MODEL_EDGE_TYPES = {"FLOWS_TO", "PROMPT_TO_MODEL_CALL", "SYSTEM_MESSAGE_OF", "USER_MESSAGE_OF"}


def classification_attributes(
    classification: str, confidence: float, reason: str, evidence: Iterable[str]
) -> dict[str, object]:
    return {
        "classification": classification,
        "confidence": round(max(0.0, min(1.0, confidence)), 2),
        "reason": reason,
        "evidence": list(dict.fromkeys(evidence)),
    }


def classify_candidate(*, name: str, path: str, source_kind: str, dynamic: bool = False) -> dict[str, object]:
    lowered, suffix = name.lower(), Path(path).suffix.lower()
    evidence = [f"identifier={name}", f"source_kind={source_kind}", "not_passed_to_model_call"]
    if suffix in {".md", ".rst"}:
        return classification_attributes("documentation", .96, "Text comes from documentation and is not connected to a model call", [f"extension={suffix}", *evidence])
    if source_kind == "json_string" or Path(path).name.lower() in {"package.json", "pyproject.toml"}:
        return classification_attributes("config_text", .94, "String is stored in project configuration and is not connected to a model call", [f"config_path={path}", *evidence])
    if any(term in lowered for term in ("error", "exception", "failure")):
        return classification_attributes("error_message", .86, "String is associated with error handling", evidence)
    if any(term in lowered for term in ("log", "debug", "diagnostic", "warning")):
        return classification_attributes("developer_message", .78, "String appears to be developer-facing diagnostic text", evidence)
    if dynamic and any(term in lowered for term in ("message", "status", "detail")):
        return classification_attributes("developer_message", .28, "Dynamic string has a message-like identifier but is not connected to an LLM call", [*evidence, "dynamic_string"])
    if any(term in lowered for term in ("button", "label", "title", "placeholder", "toast")):
        return classification_attributes("ui_text", .78, "String appears to be user-interface text", evidence)
    confidence = .58 if any(term in lowered for term in ("prompt", "instruction", "system")) else .36
    reason = "Prompt-like string is not connected to a detected LLM call"
    if dynamic:
        evidence.append("dynamic_string")
    return classification_attributes("candidate_prompt", confidence, reason, evidence)


def classify_graph_strings(graph: TokenGraph) -> None:
    """Promote only strings with a directed edge into a verified model call."""
    model_ids = {node.id for node in graph.nodes.values() if node.type == "model_call"}
    direct: dict[str, list[GraphEdge]] = {}
    for edge in graph.edges:
        if edge.target in model_ids and edge.type in MODEL_EDGE_TYPES:
            direct.setdefault(edge.source, []).append(edge)
    for node in list(graph.nodes.values()):
        if node.type not in {"prompt", "string"}:
            continue
        attrs = dict(node.attributes)
        if node.id in direct:
            roles = [str(edge.attributes.get("role", "input")) for edge in direct[node.id]]
            evidence = [item for item in attrs.get("evidence", []) if item != "not_passed_to_model_call"]
            evidence.extend(["passed_to_model_call", *[f"argument_role={role}" for role in roles]])
            attrs.update(classification_attributes("llm_prompt", .98, "String is passed to a verified LLM model call", evidence))
        elif "classification" not in attrs:
            attrs.update(classify_candidate(name=node.label, path=node.path or "", source_kind=str(attrs.get("source_kind", "unknown")), dynamic=bool(attrs.get("placeholders"))))
        if node.id not in direct and not model_ids:
            attrs["evidence"] = list(dict.fromkeys([*attrs.get("evidence", []), "no_llm_sdk_detected", "not_passed_to_model_call"]))
        graph.nodes[node.id] = replace(node, attributes=attrs)

    graph.metadata["detected_llm_sdks"] = sorted({sdk for node in graph.nodes.values() if node.type == "model_call" for sdk in node.attributes.get("sdk_imports", [])})
    graph.metadata["detected_model_calls"] = sorted({node.label for node in graph.nodes.values() if node.type == "model_call"})

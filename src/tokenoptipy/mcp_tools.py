from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .analyzer import analyze_prompt
from .counters import count_tokens
from .graph_engine import build_token_graph, compute_stats, graph_hotspots, prompt_flow, query_graph
from .graph_reporting import write_graph_outputs
from .languages import LANGUAGE_REGISTRY
from .trace import read_trace_events, trace_tool, workspace_root
from .validators import ValidationPolicy, validate_candidate

SUPPORTED_BACKENDS = {"simple", "auto", "tiktoken"}


def _backend(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in SUPPORTED_BACKENDS:
        raise ValueError(f"Unsupported token backend: {value}")
    return normalized


def _inside_workspace(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_workspace_path(value: str | Path, *, must_exist: bool = True) -> Path:
    root = workspace_root()
    candidate = Path(value).expanduser()
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not _inside_workspace(resolved, root):
        raise ValueError("Path must remain inside the configured workspace.")
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"Path not found: {resolved}")
    return resolved


def _relative(path: Path) -> str:
    return path.relative_to(workspace_root()).as_posix()


def _finding_dict(finding: Any) -> dict[str, Any]:
    data = finding.to_dict()
    return {
        "code": data.get("code"),
        "severity": data.get("severity"),
        "message": data.get("message"),
        "suggestion": data.get("suggestion"),
        "confidence": data.get("confidence"),
    }


def inspect_workspace(
    projectPath: str = ".",
    backend: str = "simple",
    limit: int = 10,
    maxFileSize: int = 1_000_000,
    buildReport: bool = False,
    includeDocumentationPrompts: bool = False,
    language: str = "auto",
    languages: list[str] | None = None,
    promptLimit: int | None = None,
) -> dict[str, Any]:
    root = workspace_root()
    project = resolve_workspace_path(projectPath)
    safe_limit = min(max(int(promptLimit if promptLimit is not None else limit), 1), 50)
    safe_size = min(max(int(maxFileSize), 1_024), 20_000_000)
    with trace_tool("inspect_workspace", root=root) as trace:
        graph = build_token_graph(
            project,
            backend=_backend(backend),
            max_file_size=safe_size,
            include_documentation_prompts=includeDocumentationPrompts,
            language=languages or language,
        )
        stats = compute_stats(graph)
        hotspots = graph_hotspots(graph, limit=safe_limit)
        findings = [
            {
                "code": finding.code,
                "severity": finding.severity,
                "node_id": finding.node_id,
                "message": finding.message,
                "suggestion": finding.suggestion,
                "estimated_saving_tokens": finding.estimated_saving_tokens,
                "confidence": finding.confidence,
            }
            for finding in graph.findings[:100]
        ]
        graph.metadata["trace_id"] = trace.trace_id
        outputs = write_graph_outputs(graph, project / "tokenoptipy-out") if buildReport else {}
        trace.set_summary(
            f"Scanned {stats['node_count']} nodes; {stats['finding_count']} findings; "
            f"{stats['total_static_prompt_tokens']} static prompt tokens"
        )
        return {
            "project_path": _relative(project),
            "backend": graph.metadata.get("backend", backend),
            "detected_languages": graph.metadata.get("detected_languages", []),
            "project_types": graph.metadata.get("project_types", []),
            "node_package_manager": graph.metadata.get("node_package_manager"),
            "files_by_language": graph.metadata.get("file_counts_by_language", {}),
            "stats": stats,
            "hotspots": hotspots,
            "findings": findings,
            "report_paths": {name: _relative(path) for name, path in outputs.items()},
            "trace_id": trace.trace_id,
            "privacy": "No source files or prompt bodies were returned.",
        }


def analyze_prompt_file(filePath: str, backend: str = "simple") -> dict[str, Any]:
    root = workspace_root()
    path = resolve_workspace_path(filePath)
    if not path.is_file():
        raise ValueError("filePath must point to a file.")
    with trace_tool("analyze_prompt_file", root=root) as trace:
        text = path.read_text(encoding="utf-8", errors="replace")
        count = count_tokens(text, backend=_backend(backend))
        findings = analyze_prompt(text)
        trace.set_summary(f"Analyzed {_relative(path)}; {count.tokens} tokens; {len(findings)} findings")
        return {
            "file_path": _relative(path),
            "token_count": count.to_dict(),
            "findings": [_finding_dict(finding) for finding in findings],
            "privacy": "The prompt text was analyzed locally and was not returned or logged.",
        }


def _load_text(text: str, path: str, *, label: str) -> tuple[str, str]:
    if text and path:
        raise ValueError(f"Provide either {label}Text or {label}Path, not both.")
    if path:
        resolved = resolve_workspace_path(path)
        if not resolved.is_file():
            raise ValueError(f"{label}Path must point to a file.")
        return resolved.read_text(encoding="utf-8", errors="replace"), _relative(resolved)
    if not text:
        raise ValueError(f"Provide {label}Text or {label}Path.")
    return text, "inline"


def validate_prompt_change(
    originalText: str = "",
    candidateText: str = "",
    originalPath: str = "",
    candidatePath: str = "",
    backend: str = "simple",
    requiredTerms: list[str] | None = None,
    minSemanticScore: float = 0.72,
) -> dict[str, Any]:
    root = workspace_root()
    with trace_tool("validate_prompt_change", root=root) as trace:
        original, original_label = _load_text(originalText, originalPath, label="original")
        candidate, candidate_label = _load_text(candidateText, candidatePath, label="candidate")
        selected_backend = _backend(backend)
        original_count = count_tokens(original, backend=selected_backend)
        candidate_count = count_tokens(candidate, backend=selected_backend)
        policy = ValidationPolicy(
            min_semantic_score=min(max(float(minSemanticScore), 0.0), 1.0),
            required_terms=tuple(requiredTerms or ()),
        )
        validation = validate_candidate(original, candidate, policy)
        saved = original_count.tokens - candidate_count.tokens
        percent = saved / original_count.tokens * 100 if original_count.tokens else 0.0
        trace.set_summary(
            f"Validation {'passed' if validation.valid else 'failed'}; "
            f"{saved:+d} tokens ({percent:+.1f}%)"
        )
        return {
            "valid": validation.valid,
            "original_source": original_label,
            "candidate_source": candidate_label,
            "original_tokens": original_count.tokens,
            "candidate_tokens": candidate_count.tokens,
            "saved_tokens": saved,
            "savings_percent": round(percent, 3),
            "validation": validation.to_dict(),
            "privacy": "Prompt bodies were not returned or logged.",
        }


def query_token_flow(
    query: str,
    projectPath: str = ".",
    backend: str = "simple",
    limit: int = 20,
    language: str = "auto",
) -> dict[str, Any]:
    root = workspace_root()
    if not query.strip():
        raise ValueError("query must not be empty.")
    project = resolve_workspace_path(projectPath)
    safe_limit = min(max(int(limit), 1), 50)
    with trace_tool("query_token_flow", root=root) as trace:
        graph = build_token_graph(project, backend=_backend(backend), language=language)
        matches = query_graph(graph, query, limit=safe_limit)
        term_count = len(re.findall(r"[\w.-]+", query, flags=re.UNICODE))
        trace.set_summary(f"Queried {term_count} term(s); returned {len(matches)} graph matches")
        return {
            "project_path": _relative(project),
            "matches": matches,
            "privacy": "The query text is not written to the trace log.",
        }


def get_traceability(limit: int = 20) -> dict[str, Any]:
    root = workspace_root()
    with trace_tool("get_traceability", root=root) as trace:
        events = read_trace_events(limit=min(max(int(limit), 1), 100), root=root)
        trace.set_summary(f"Returned {len(events)} recent trace events")
        return {
            "events": events,
            "privacy": "Trace events contain tool metadata only, never prompt bodies or tool arguments.",
        }


def get_prompt_flow(
    prompt: str,
    projectPath: str = ".",
    backend: str = "simple",
    includeDocumentationPrompts: bool = False,
    language: str = "auto",
    languages: list[str] | None = None,
) -> dict[str, Any]:
    root = workspace_root()
    project = resolve_workspace_path(projectPath)
    with trace_tool("get_prompt_flow", root=root) as trace:
        graph = build_token_graph(
            project,
            backend=_backend(backend),
            include_documentation_prompts=includeDocumentationPrompts,
            language=languages or language,
        )
        result = prompt_flow(graph, prompt)
        result["trace_id"] = trace.trace_id
        result["privacy"] = "No complete prompt body or sensitive tool argument was returned or logged."
        trace.set_summary(
            f"Prompt flow {result['node_id']}; {len(result['connected_nodes'])} connected nodes; "
            f"{result['total_flow_tokens']} tokens"
        )
        return result


def build_graph_report(
    projectPath: str = ".",
    outputPath: str = "tokenoptipy-out",
    backend: str = "simple",
    includeDocumentationPrompts: bool = False,
    language: str = "auto",
    outputDir: str = "",
    languages: list[str] | None = None,
) -> dict[str, Any]:
    root = workspace_root()
    project = resolve_workspace_path(projectPath)
    output = resolve_workspace_path(outputDir or outputPath, must_exist=False)
    with trace_tool("build_graph_report", root=root) as trace:
        graph = build_token_graph(
            project,
            backend=_backend(backend),
            include_documentation_prompts=includeDocumentationPrompts,
            language=languages or language,
        )
        graph.metadata["trace_id"] = trace.trace_id
        outputs = write_graph_outputs(graph, output)
        stats = compute_stats(graph)
        trace.set_summary(
            f"Built graph report; {stats['node_count']} nodes; {stats['edge_count']} edges"
        )
        return {
            "project_path": _relative(project),
            "outputs": {name: _relative(path) for name, path in outputs.items()},
            "stats": stats,
            "detected_languages": graph.metadata.get("detected_languages", []),
            "project_types": graph.metadata.get("project_types", []),
            "files_by_language": graph.metadata.get("file_counts_by_language", {}),
            "trace_id": trace.trace_id,
            "privacy": "Reports contain redacted previews only; complete prompt bodies are excluded.",
        }


def get_language_support(projectPath: str = ".") -> dict[str, Any]:
    root = workspace_root()
    project = resolve_workspace_path(projectPath)
    with trace_tool("get_language_support", root=root) as trace:
        diagnostics = LANGUAGE_REGISTRY.diagnostics(project)
        available = {str(item["language"]): str(item["parser"]) for item in diagnostics if item["available"]}
        unavailable = {str(item["language"]): str(item["unavailable_reason"] or "parser unavailable") for item in diagnostics if not item["available"]}
        counts = {str(item["language"]): item["files_detected"] for item in diagnostics}
        detected = [language for language, count in counts.items() if isinstance(count, int) and count]
        total = sum(count for count in counts.values() if isinstance(count, int))
        trace.set_summary(f"Detected {len(detected)} language(s); {total} source files")
        return {"supported_languages": list(LANGUAGE_REGISTRY.language_ids), "detected_languages": detected, "available_parsers": available, "unavailable_parsers": unavailable, "file_counts": counts, "trace_id": trace.trace_id}

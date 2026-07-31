from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .analyzer import analyze_prompt
from .counters import count_tokens
from .graph_engine import build_token_graph, compute_stats, graph_hotspots, query_graph
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
) -> dict[str, Any]:
    root = workspace_root()
    project = resolve_workspace_path(projectPath)
    safe_limit = min(max(int(limit), 1), 50)
    safe_size = min(max(int(maxFileSize), 1_024), 20_000_000)
    with trace_tool("inspect_workspace", root=root) as trace:
        graph = build_token_graph(
            project,
            backend=_backend(backend),
            max_file_size=safe_size,
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
        trace.set_summary(
            f"Scanned {stats['node_count']} nodes; {stats['finding_count']} findings; "
            f"{stats['total_static_prompt_tokens']} static prompt tokens"
        )
        return {
            "project_path": _relative(project),
            "backend": graph.metadata.get("backend", backend),
            "stats": stats,
            "hotspots": hotspots,
            "findings": findings,
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
) -> dict[str, Any]:
    root = workspace_root()
    if not query.strip():
        raise ValueError("query must not be empty.")
    project = resolve_workspace_path(projectPath)
    safe_limit = min(max(int(limit), 1), 50)
    with trace_tool("query_token_flow", root=root) as trace:
        graph = build_token_graph(project, backend=_backend(backend))
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

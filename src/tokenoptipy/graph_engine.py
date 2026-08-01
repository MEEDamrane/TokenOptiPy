from __future__ import annotations

import json
import re
from collections import Counter, defaultdict, deque
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .counters import count_tokens
from .graph_models import GraphEdge, GraphFinding, GraphNode, TokenGraph
from .javascript_extractor import extract_javascript_file
from .privacy import redact_preview
from .project_config import LANGUAGES, detect_project, load_project_config
from .python_extractor import (
    content_hash,
    extract_python_file,
    minhash_signature,
    stable_id,
    term_hashes,
)
from .scanner import ProjectFile, project_fingerprint, scan_project

PROMPT_KEY_RE = re.compile(
    r"^(?:"
    r".*[_-])?"
    r"(?:prompt|prompts|instruction|instructions|system|system_prompt|"
    r"message|messages|context|template|history|conversation)"
    r"(?:[_-].*)?$",
    re.IGNORECASE,
)
PROMPT_CONTENT_RE = re.compile(
    r"(?:\byou are\b|\breturn only\b|\brespond with\b|\bsystem message\b|"
    r"\binstructions?\s*:|\br[ée]ponds?\b|\banalyse\b)",
    re.IGNORECASE,
)
PROMPT_FILE_EXTENSIONS = {".prompt", ".jinja", ".jinja2", ".j2"}


def file_node(item: ProjectFile) -> GraphNode:
    return GraphNode(
        id=f"file:{item.relative_path}",
        type="file",
        label=item.relative_path,
        path=item.relative_path,
        attributes={
            "root_file": item.relative_path,
            "extension": item.extension,
            "size_bytes": item.size_bytes,
            "sha256": item.sha256,
        },
    )


def text_prompt_node(item: ProjectFile, text: str, backend: str) -> GraphNode:
    count = count_tokens(text, backend=backend)
    preview, has_secret = redact_preview(text)
    return GraphNode(
        id=stable_id("prompt", item.relative_path, "whole_file"),
        type="prompt",
        label=Path(item.relative_path).name,
        path=item.relative_path,
        line=1,
        end_line=max(1, text.count("\n") + 1),
        static_tokens=count.tokens,
        attributes={
            "root_file": item.relative_path,
            "source_kind": "prompt_file",
            "preview": preview,
            "content_hash": content_hash(text),
            "minhash": minhash_signature(text),
            "term_hashes": term_hashes(text),
            "characters": len(text),
            "has_possible_secret": has_secret,
        },
    )


def extract_json_strings(value: Any, prefix: str = "$") -> list[tuple[str, str]]:
    strings: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            strings.extend(extract_json_strings(item, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            strings.extend(extract_json_strings(item, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        strings.append((prefix, value))
    return strings


def should_extract_json_string(json_path: str, text: str) -> bool:
    leaf = re.split(r"[.\[]", json_path)[-1].rstrip("]")
    message_content = bool(
        re.search(r"\.(?:message|messages)(?:\[\d+\])?\.content$", json_path, re.IGNORECASE)
    )
    return bool(PROMPT_KEY_RE.fullmatch(leaf)) or message_content or len(text) >= 120


def should_extract_text_file(
    item: ProjectFile,
    text: str,
    *,
    include_documentation_prompts: bool = False,
) -> bool:
    if item.extension in PROMPT_FILE_EXTENSIONS:
        return True
    if item.extension == ".txt":
        return True
    path_terms = re.split(r"[/_.-]", item.relative_path)
    if item.extension == ".md":
        in_prompt_directory = any(
            part.lower() in {"prompt", "prompts"}
            for part in Path(item.relative_path).parts[:-1]
        )
        prompt_named = any(
            term in Path(item.relative_path).stem.lower()
            for term in ("prompt", "system", "instruction", "agent", "template")
        )
        return bool(
            include_documentation_prompts
            or in_prompt_directory
            or prompt_named
            or PROMPT_CONTENT_RE.search(text)
        )
    if any(PROMPT_KEY_RE.fullmatch(term) for term in path_terms if term):
        return True
    if PROMPT_CONTENT_RE.search(text):
        return True
    if item.extension in {".yaml", ".yml"}:
        return any(
            PROMPT_KEY_RE.fullmatch(key.strip())
            for key in re.findall(r"^\s*([\w-]+)\s*:", text, re.MULTILINE)
        )
    return False


def build_token_graph(
    root: str | Path,
    *,
    backend: str = "simple",
    max_file_size: int = 1_000_000,
    include_hidden: bool = False,
    include_documentation_prompts: bool = False,
    language: str = "auto",
) -> TokenGraph:
    project_root = Path(root).expanduser().resolve()
    if language not in LANGUAGES:
        raise ValueError(f"Unsupported language: {language}. Choose auto, python, javascript, typescript, or all.")
    config = load_project_config(project_root)
    selected = set(config.languages) if language == "auto" and config.languages else ({language} if language not in {"auto", "all"} else set())
    extensions = None
    if selected:
        mapping = {"python": {".py"}, "javascript": {".js", ".jsx", ".mjs", ".cjs"}, "typescript": {".ts", ".tsx"}}
        extensions = set().union(*(mapping[item] for item in selected)) | {".txt", ".md", ".json", ".yaml", ".yml", ".prompt", ".jinja", ".jinja2", ".j2"}
    files = scan_project(
        project_root,
        max_file_size=max_file_size,
        include_hidden=include_hidden,
        extensions=extensions,
        exclude=set(config.exclude),
    )
    graph = TokenGraph(project_root=str(project_root))
    graph.metadata.update(
        {
            "backend": backend,
            "file_count": len(files),
            "project_fingerprint": project_fingerprint(files),
            "parser": "Python ast + Tree-sitter JavaScript/TypeScript grammars",
            "language": language,
        }
    )
    graph.metadata.update(detect_project(project_root, {item.extension for item in files}))
    graph.metadata["file_counts_by_language"] = {
        "python": sum(item.extension == ".py" for item in files),
        "javascript": sum(item.extension in {".js", ".jsx", ".mjs", ".cjs"} for item in files),
        "typescript": sum(item.extension in {".ts", ".tsx"} for item in files),
    }

    for item in files:
        graph.add_node(file_node(item))
        if item.extension == ".py":
            extraction = extract_python_file(
                item.absolute_path,
                item.relative_path,
                backend=backend,
            )
            for node in extraction.nodes:
                graph.add_node(node)
            for edge in extraction.edges:
                graph.add_edge(edge)
            continue

        if item.extension in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
            js_extraction = extract_javascript_file(item.absolute_path, item.relative_path, backend=backend)
            for node in js_extraction.nodes:
                graph.add_node(node)
            for edge in js_extraction.edges:
                graph.add_edge(edge)
            for module, _kind, _local in js_extraction.imports:
                if module.startswith("."):
                    _link_local_import(graph, project_root, item.relative_path, module)
            continue

        text = item.absolute_path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            continue

        if item.extension == ".json":
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if parsed is not None:
                extracted = [
                    (json_path, value)
                    for json_path, value in extract_json_strings(parsed)
                    if should_extract_json_string(json_path, value)
                ]
                for json_path, value in extracted:
                    count = count_tokens(value, backend=backend)
                    preview, has_secret = redact_preview(value)
                    prompt_id = stable_id("prompt", item.relative_path, json_path)
                    graph.add_node(
                        GraphNode(
                            id=prompt_id,
                            type="prompt",
                            label=f"{Path(item.relative_path).name}:{json_path}",
                            path=item.relative_path,
                            static_tokens=count.tokens,
                            attributes={
                                "root_file": item.relative_path,
                                "source_kind": "json_string",
                                "json_path": json_path,
                                "preview": preview,
                                "content_hash": content_hash(value),
                                "minhash": minhash_signature(value),
                                "term_hashes": term_hashes(value),
                                "characters": len(value),
                                "has_possible_secret": has_secret,
                            },
                        )
                    )
                    graph.add_edge(
                        GraphEdge(f"file:{item.relative_path}", prompt_id, "CONTAINS_PROMPT")
                    )
                if extracted:
                    continue

        if should_extract_text_file(
            item,
            text,
            include_documentation_prompts=include_documentation_prompts,
        ):
            prompt = text_prompt_node(item, text, backend)
            graph.add_node(prompt)
            graph.add_edge(
                GraphEdge(f"file:{item.relative_path}", prompt.id, "CONTAINS_PROMPT")
            )

    link_file_prompt_references(graph)
    add_duplicate_edges(graph)
    add_graph_findings(graph)
    graph.metadata.update(compute_stats(graph))
    return graph


def _link_local_import(graph: TokenGraph, root: Path, source: str, module: str) -> None:
    base = (root / Path(source).parent / module).resolve()
    try:
        base.relative_to(root)
    except ValueError:
        return
    candidates = [base] if base.suffix else [base.with_suffix(ext) for ext in (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")]
    candidates += [base / f"index{ext}" for ext in (".js", ".ts", ".jsx", ".tsx")]
    for candidate in candidates:
        if candidate.is_file():
            target = candidate.relative_to(root).as_posix()
            graph.add_edge(GraphEdge(f"file:{source}", f"file:{target}", "IMPORTS"))
            return


def link_file_prompt_references(graph: TokenGraph) -> None:
    file_prompts: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        if edge.type == "CONTAINS_PROMPT" and edge.source.startswith("file:"):
            file_prompts[edge.source.removeprefix("file:")].append(edge.target)

    for node in list(graph.nodes.values()):
        loaded_path = node.attributes.get("loaded_path")
        if not isinstance(loaded_path, str) or not node.path:
            continue
        normalized = Path(loaded_path).as_posix().lstrip("./")
        source_relative = (Path(node.path).parent / loaded_path).as_posix().lstrip("./")
        candidates = [normalized, source_relative]
        matched: list[str] = []
        for candidate in candidates:
            if candidate in file_prompts:
                matched = file_prompts[candidate]
                break
        if not matched:
            suffix_matches = [
                prompt_ids
                for relative_path, prompt_ids in file_prompts.items()
                if relative_path.endswith("/" + normalized) or relative_path == normalized
            ]
            if len(suffix_matches) == 1:
                matched = suffix_matches[0]
        for prompt_id in matched:
            graph.add_edge(GraphEdge(prompt_id, node.id, "LOADED_AS"))


def expanded_static_tokens(
    graph: TokenGraph,
    node_id: str,
    visited: set[str] | None = None,
) -> int:
    seen = visited or set()
    if node_id in seen:
        return 0
    seen.add(node_id)
    node = graph.nodes.get(node_id)
    if node is None:
        return 0
    total = node.static_tokens
    for edge in graph.edges:
        if edge.target == node_id and edge.type in {"INCLUDES", "LOADED_AS"}:
            total += expanded_static_tokens(graph, edge.source, seen)
    return total


def prompt_nodes(graph: TokenGraph) -> list[GraphNode]:
    return [node for node in graph.nodes.values() if node.type == "prompt"]


def prompt_flow(graph: TokenGraph, prompt: str) -> dict[str, Any]:
    """Return a privacy-safe, directed neighborhood and model-call paths for one prompt."""
    node = resolve_node(graph, prompt)
    if node.type != "prompt":
        raise ValueError(f"Node is not a prompt: {node.id}")
    incoming = [edge for edge in graph.edges if edge.target == node.id]
    outgoing = [edge for edge in graph.edges if edge.source == node.id]
    adjacent_ids = {edge.source for edge in incoming} | {edge.target for edge in outgoing}
    connected = [graph.nodes[item] for item in sorted(adjacent_ids) if item in graph.nodes]

    adjacency: dict[str, list[GraphEdge]] = defaultdict(list)
    for edge in graph.edges:
        adjacency[edge.source].append(edge)
    queue: deque[tuple[str, list[str], list[str]]] = deque([(node.id, [node.id], [])])
    visited = {node.id}
    paths: list[dict[str, Any]] = []
    model_calls: dict[str, GraphNode] = {}
    while queue:
        current, nodes_path, relations = queue.popleft()
        for edge in adjacency[current]:
            next_node = graph.nodes.get(edge.target)
            if next_node is None:
                continue
            next_path = [*nodes_path, next_node.id]
            next_relations = [*relations, edge.type]
            if next_node.type == "model_call":
                model_calls[next_node.id] = next_node
                paths.append({"nodes": next_path, "relations": next_relations})
            if next_node.id not in visited and len(next_path) <= 12:
                visited.add(next_node.id)
                queue.append((next_node.id, next_path, next_relations))

    flow_ids = {node.id, *adjacent_ids}
    for path in paths:
        flow_ids.update(path["nodes"])
    flow_nodes = [graph.nodes[item] for item in flow_ids if item in graph.nodes]
    return {
        "node_id": node.id,
        "prompt_node": node.to_dict(),
        "incoming_edges": [edge.to_dict() for edge in incoming],
        "outgoing_edges": [edge.to_dict() for edge in outgoing],
        "connected_nodes": [item.to_dict() for item in connected],
        "relation_types": sorted({edge.type for edge in [*incoming, *outgoing]}),
        "prompt_tokens": node.static_tokens,
        "connected_node_tokens": {item.id: item.static_tokens for item in connected},
        "total_flow_tokens": sum(item.static_tokens for item in flow_nodes),
        "model_calls": [item.to_dict() for item in model_calls.values()],
        "model_call_paths": paths,
        "findings": [item.to_dict() for item in graph.findings if item.node_id in flow_ids],
    }


def add_duplicate_edges(graph: TokenGraph, threshold: float = 0.72) -> None:
    prompts = [node for node in prompt_nodes(graph) if node.static_tokens >= 20][:500]
    for index, left in enumerate(prompts):
        left_preview = str(left.attributes.get("preview", ""))
        for right in prompts[index + 1 :]:
            if left.attributes.get("content_hash") == right.attributes.get("content_hash"):
                similarity = 1.0
            else:
                left_signature = left.attributes.get("minhash", [])
                right_signature = right.attributes.get("minhash", [])
                if left_signature and len(left_signature) == len(right_signature):
                    similarity = sum(
                        left_value == right_value
                        for left_value, right_value in zip(
                            left_signature, right_signature, strict=False
                        )
                    ) / len(left_signature)
                    left_terms = set(left.attributes.get("term_hashes", []))
                    right_terms = set(right.attributes.get("term_hashes", []))
                    if left_terms and right_terms:
                        containment = len(left_terms & right_terms) / min(
                            len(left_terms), len(right_terms)
                        )
                        similarity = max(similarity, containment)
                else:
                    right_preview = str(right.attributes.get("preview", ""))
                    similarity = SequenceMatcher(None, left_preview, right_preview).ratio()
            if similarity >= threshold:
                graph.add_edge(
                    GraphEdge(
                        left.id,
                        right.id,
                        "DUPLICATES",
                        {"similarity": round(similarity, 4)},
                    )
                )


def add_graph_findings(graph: TokenGraph) -> None:
    for node in prompt_nodes(graph):
        preview = str(node.attributes.get("preview", ""))
        if node.static_tokens >= 1_000:
            graph.add_finding(
                GraphFinding(
                    code="TG001",
                    severity="warning",
                    node_id=node.id,
                    message=f"Large static prompt: {node.static_tokens} estimated tokens.",
                    suggestion="Split stable instructions from dynamic context and retrieve only relevant data.",
                    estimated_saving_tokens=max(0, node.static_tokens // 3),
                    confidence=0.85,
                )
            )
        example_count = len(re.findall(r"\b(?:example|exemple)\s*\d*\s*[:.-]", preview, re.IGNORECASE))
        if example_count >= 4:
            graph.add_finding(
                GraphFinding(
                    code="TG003",
                    severity="review",
                    node_id=node.id,
                    message=f"At least {example_count} few-shot examples detected in the prompt preview.",
                    suggestion="Evaluate whether a smaller, more diverse example set preserves task quality.",
                    estimated_saving_tokens=node.static_tokens // 4,
                    confidence=0.65,
                )
            )
        placeholders = node.attributes.get("placeholders", [])
        if isinstance(placeholders, list) and len(placeholders) >= 5:
            graph.add_finding(
                GraphFinding(
                    code="TG006",
                    severity="info",
                    node_id=node.id,
                    message=f"Prompt depends on {len(placeholders)} dynamic values.",
                    suggestion="Measure each dynamic component separately and cap unbounded values.",
                    confidence=0.8,
                )
            )
        if node.attributes.get("has_possible_secret"):
            graph.add_finding(
                GraphFinding(
                    code="SEC001",
                    severity="critical",
                    node_id=node.id,
                    message="Possible secret detected. The preview was redacted.",
                    suggestion="Remove credentials from prompts and rotate exposed secrets.",
                    confidence=0.8,
                )
            )

    for edge in graph.edges:
        if edge.type != "DUPLICATES":
            continue
        left = graph.nodes.get(edge.source)
        right = graph.nodes.get(edge.target)
        if left is None or right is None:
            continue
        saving = min(left.static_tokens, right.static_tokens)
        graph.add_finding(
            GraphFinding(
                code="TG002",
                severity="review",
                node_id=right.id,
                message=(
                    f"Prompt overlaps with '{left.label}' "
                    f"({float(edge.attributes.get('similarity', 0)):.0%} similarity)."
                ),
                suggestion="Extract shared instructions or keep one canonical prompt.",
                estimated_saving_tokens=saving,
                confidence=float(edge.attributes.get("similarity", 0.72)),
            )
        )

    incoming_by_call: dict[str, list[GraphNode]] = defaultdict(list)
    for edge in graph.edges:
        if edge.type == "FLOWS_TO" and edge.target in graph.nodes:
            source = graph.nodes.get(edge.source)
            if source is not None:
                incoming_by_call[edge.target].append(source)

    for call_id, sources in incoming_by_call.items():
        call = graph.nodes.get(call_id)
        if call is None or call.type != "model_call":
            continue
        total = sum(expanded_static_tokens(graph, source.id) for source in sources)
        dynamic = [
            source for source in sources if bool(source.attributes.get("dynamic"))
        ]
        attributes = dict(call.attributes)
        attributes["estimated_static_input_tokens"] = total
        attributes["dynamic_inputs"] = [source.label for source in dynamic]
        graph.nodes[call_id] = GraphNode(
            id=call.id,
            type=call.type,
            label=call.label,
            path=call.path,
            line=call.line,
            end_line=call.end_line,
            static_tokens=total,
            attributes=attributes,
        )
        for source in dynamic:
            if re.search(r"history|messages|conversation", source.label, re.IGNORECASE):
                graph.add_finding(
                    GraphFinding(
                        code="TG005",
                        severity="warning",
                        node_id=source.id,
                        message=f"Potentially unbounded conversation input flows to '{call.label}'.",
                        suggestion="Apply a message window, summarization, or explicit token budget.",
                        confidence=0.72,
                    )
                )


def compute_stats(graph: TokenGraph) -> dict[str, Any]:
    node_types = Counter(node.type for node in graph.nodes.values())
    edge_types = Counter(edge.type for edge in graph.edges)
    prompts = prompt_nodes(graph)
    return {
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "finding_count": len(graph.findings),
        "node_types": dict(sorted(node_types.items())),
        "edge_types": dict(sorted(edge_types.items())),
        "prompt_count": len(prompts),
        "total_static_prompt_tokens": sum(node.static_tokens for node in prompts),
    }


def load_graph(path: str | Path) -> TokenGraph:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return TokenGraph.from_dict(data)


def resolve_node(graph: TokenGraph, query: str) -> GraphNode:
    if query in graph.nodes:
        return graph.nodes[query]
    matches = [
        node
        for node in graph.nodes.values()
        if query.lower() == node.label.lower()
    ]
    if not matches:
        matches = [
            node
            for node in graph.nodes.values()
            if query.lower() in node.label.lower()
            or (node.path and query.lower() in node.path.lower())
        ]
    if not matches:
        raise KeyError(f"Node not found: {query}")
    if len(matches) > 1:
        labels = ", ".join(node.id for node in matches[:8])
        raise KeyError(f"Ambiguous node '{query}'. Matches: {labels}")
    return matches[0]


def graph_hotspots(graph: TokenGraph, limit: int = 10) -> list[dict[str, Any]]:
    candidates = [
        node
        for node in graph.nodes.values()
        if node.type in {"prompt", "model_call"}
    ]
    candidates.sort(key=lambda node: node.static_tokens, reverse=True)
    return [
        {
            "id": node.id,
            "type": node.type,
            "label": node.label,
            "path": node.path,
            "line": node.line,
            "static_tokens": node.static_tokens,
            "preview": node.attributes.get("preview"),
            "dynamic_inputs": node.attributes.get("dynamic_inputs", []),
        }
        for node in candidates[:limit]
    ]


def shortest_path(graph: TokenGraph, source_query: str, target_query: str) -> list[dict[str, Any]]:
    source = resolve_node(graph, source_query)
    target = resolve_node(graph, target_query)
    adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in graph.edges:
        adjacency[edge.source].append((edge.target, edge.type))
        adjacency[edge.target].append((edge.source, edge.type))

    queue: deque[str] = deque([source.id])
    previous: dict[str, tuple[str, str] | None] = {source.id: None}
    while queue:
        current = queue.popleft()
        if current == target.id:
            break
        for neighbor, edge_type in adjacency[current]:
            if neighbor not in previous:
                previous[neighbor] = (current, edge_type)
                queue.append(neighbor)

    if target.id not in previous:
        return []

    node_ids: list[str] = []
    cursor: str | None = target.id
    while cursor is not None:
        node_ids.append(cursor)
        entry = previous[cursor]
        cursor = entry[0] if entry else None
    node_ids.reverse()

    result: list[dict[str, Any]] = []
    for index, node_id in enumerate(node_ids):
        node = graph.nodes[node_id]
        output_edge_type: str | None = None
        if index > 0:
            path_entry = previous[node_id]
            output_edge_type = path_entry[1] if path_entry else None
        result.append(
            {
                "id": node.id,
                "type": node.type,
                "label": node.label,
                "via": output_edge_type,
            }
        )
    return result


def query_graph(graph: TokenGraph, text: str, limit: int = 20) -> list[dict[str, Any]]:
    terms = [term.lower() for term in re.findall(r"[\w.-]+", text) if len(term) > 1]
    scored: list[tuple[int, GraphNode]] = []
    for node in graph.nodes.values():
        haystack = " ".join(
            [
                node.id,
                node.type,
                node.label,
                node.path or "",
                str(node.attributes.get("preview", "")),
            ]
        ).lower()
        score = sum(3 if term in node.label.lower() else 1 for term in terms if term in haystack)
        if score:
            scored.append((score, node))
    scored.sort(key=lambda item: (item[0], item[1].static_tokens), reverse=True)
    return [
        {
            "score": score,
            "id": node.id,
            "type": node.type,
            "label": node.label,
            "path": node.path,
            "line": node.line,
            "static_tokens": node.static_tokens,
            "preview": node.attributes.get("preview"),
        }
        for score, node in scored[:limit]
    ]


def aggregate_hash(root: str | Path, max_file_size: int = 1_000_000) -> str:
    return project_fingerprint(scan_project(root, max_file_size=max_file_size))

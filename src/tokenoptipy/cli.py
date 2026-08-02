from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyzer import analyze_prompt
from .counters import count_tokens
from .evaluation import evaluate_jsonl
from .graph_engine import (
    aggregate_hash,
    build_token_graph,
    compute_stats,
    graph_hotspots,
    load_graph,
    prompt_flow,
    query_graph,
    resolve_node,
    shortest_path,
)
from .graph_reporting import write_graph_outputs
from .integrations import AGENT_PATHS, CLIENT_PATHS, write_agent_instructions, write_mcp_configs
from .languages import LANGUAGE_REGISTRY
from .optimizer import optimize_prompt
from .reporting import format_summary, write_json_report
from .validators import ValidationPolicy

DEFAULT_GRAPH_PATH = "tokenoptipy-out/graph.json"


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def print_json(data: object) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tokenoptipy",
        description=(
            "Build a local token-flow graph, find prompt hotspots, and safely reduce prompt tokens."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version="TokenOptiPy 0.5.0",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_command = subparsers.add_parser(
        "build",
        help="Scan a project and build its TokenGraph.",
    )
    build_command.add_argument("path", nargs="?", default=".")
    build_command.add_argument("--output", default="tokenoptipy-out")
    build_command.add_argument("--backend", default="simple", choices=["simple", "auto", "tiktoken"])
    build_command.add_argument("--max-file-size", type=int, default=1_000_000)
    build_command.add_argument("--include-hidden", action="store_true")
    build_command.add_argument("--language", action="append", choices=["auto", "all", *LANGUAGE_REGISTRY.language_ids], help="Language to analyze; repeat for multiple languages (default: auto).")
    build_command.add_argument(
        "--include-documentation-prompts",
        action="store_true",
        help="Treat Markdown documentation as prompt content.",
    )
    build_command.add_argument(
        "--update",
        action="store_true",
        help="Skip rebuilding when the project fingerprint has not changed.",
    )

    stats_command = subparsers.add_parser("stats", help="Show TokenGraph statistics.")
    stats_command.add_argument("--graph", default=DEFAULT_GRAPH_PATH)
    stats_command.add_argument("--json", action="store_true", dest="as_json")

    hotspots_command = subparsers.add_parser(
        "hotspots",
        help="List the most token-heavy prompts and model calls.",
    )
    hotspots_command.add_argument("--graph", default=DEFAULT_GRAPH_PATH)
    hotspots_command.add_argument("--limit", type=int, default=10)
    hotspots_command.add_argument("--json", action="store_true", dest="as_json")

    explain_command = subparsers.add_parser("explain", help="Explain one graph node.")
    explain_command.add_argument("node")
    explain_command.add_argument("--graph", default=DEFAULT_GRAPH_PATH)

    path_command = subparsers.add_parser("path", help="Find a path between two graph nodes.")
    path_command.add_argument("source")
    path_command.add_argument("target")
    path_command.add_argument("--graph", default=DEFAULT_GRAPH_PATH)

    query_command = subparsers.add_parser(
        "query",
        help="Search the graph locally using keywords.",
    )
    query_command.add_argument("text")
    query_command.add_argument("--graph", default=DEFAULT_GRAPH_PATH)
    query_command.add_argument("--limit", type=int, default=20)

    flow_command = subparsers.add_parser("prompt-flow", help="Show the complete flow for a prompt.")
    flow_command.add_argument("prompt")
    flow_command.add_argument("--graph", default=DEFAULT_GRAPH_PATH)

    count_parser = subparsers.add_parser("count", help="Count prompt tokens.")
    count_parser.add_argument("path", help="Text file path or - for stdin.")
    count_parser.add_argument("--backend", default="auto", choices=["auto", "simple", "tiktoken"])
    count_parser.add_argument("--model")
    count_parser.add_argument("--json", action="store_true", dest="as_json")

    analyze_parser = subparsers.add_parser("analyze", help="Analyze one prompt for token waste.")
    analyze_parser.add_argument("path", help="Text file path or - for stdin.")
    analyze_parser.add_argument("--json", action="store_true", dest="as_json")

    optimize_parser = subparsers.add_parser(
        "optimize",
        help="Generate and validate shorter candidates for one prompt.",
    )
    optimize_parser.add_argument("path", help="Text file path or - for stdin.")
    optimize_parser.add_argument("--backend", default="auto", choices=["auto", "simple", "tiktoken"])
    optimize_parser.add_argument("--model")
    optimize_parser.add_argument("--output", help="Write the selected prompt to this path.")
    optimize_parser.add_argument("--report", help="Write a JSON report to this path.")
    optimize_parser.add_argument("--min-semantic-score", type=float, default=0.72)
    optimize_parser.add_argument("--required-term", action="append", default=[])

    compare_parser = subparsers.add_parser("compare", help="Compare two prompt files.")
    compare_parser.add_argument("original")
    compare_parser.add_argument("optimized")
    compare_parser.add_argument("--backend", default="auto", choices=["auto", "simple", "tiktoken"])
    compare_parser.add_argument("--model")

    evaluate_parser = subparsers.add_parser(
        "evaluate",
        help="Aggregate task quality, tokens, and latency from JSONL results.",
    )
    evaluate_parser.add_argument("path", help="Evaluation JSONL file.")

    mcp_config = subparsers.add_parser("mcp-config", help="Generate MCP stdio client configurations.")
    mcp_config.add_argument("path", nargs="?", default=".")
    mcp_config.add_argument("--client", action="append", choices=["all", "codex", *CLIENT_PATHS], default=[])
    mcp_config.add_argument("--python", default=sys.executable)

    agent_init = subparsers.add_parser("agent-init", help="Generate instructions for coding agents.")
    agent_init.add_argument("path", nargs="?", default=".")
    agent_init.add_argument("--client", action="append", choices=["all", *AGENT_PATHS], default=[])

    languages_command = subparsers.add_parser("languages", help="Show language parser support and detected files.")
    languages_command.add_argument("path", nargs="?", default=".")
    languages_command.add_argument("--json", action="store_true", dest="as_json")

    return parser


def run_build(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    state_path = output_dir / ".tokenoptipy-state.json"
    current_fingerprint = aggregate_hash(args.path, max_file_size=args.max_file_size)

    if args.update and state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("project_fingerprint") == current_fingerprint:
            print(f"TokenGraph is already current: {output_dir / 'graph.json'}")
            return 0

    graph = build_token_graph(
        args.path,
        backend=args.backend,
        max_file_size=args.max_file_size,
        include_hidden=args.include_hidden,
        include_documentation_prompts=args.include_documentation_prompts,
        language=args.language or ["auto"],
    )
    outputs = write_graph_outputs(graph, output_dir)
    state_path.write_text(
        json.dumps(
            {
                "project_root": graph.project_root,
                "project_fingerprint": graph.metadata.get("project_fingerprint"),
                "version": graph.version,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    stats = compute_stats(graph)
    print(
        f"Built TokenGraph: {stats['node_count']} nodes, {stats['edge_count']} edges, "
        f"{stats['prompt_count']} prompts, {stats['total_static_prompt_tokens']} static tokens."
    )
    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0


def run_stats(args: argparse.Namespace) -> int:
    graph = load_graph(args.graph)
    stats = compute_stats(graph)
    if args.as_json:
        print_json(stats)
    else:
        print(f"Project: {graph.project_root}")
        print(f"Nodes: {stats['node_count']}")
        print(f"Edges: {stats['edge_count']}")
        print(f"Prompts: {stats['prompt_count']}")
        print(f"Static prompt tokens: {stats['total_static_prompt_tokens']}")
        print(f"Findings: {stats['finding_count']}")
        print("Node types:")
        for node_type, count in stats["node_types"].items():
            print(f"  {node_type}: {count}")
    return 0


def run_languages(args: argparse.Namespace) -> int:
    diagnostics = LANGUAGE_REGISTRY.diagnostics(Path(args.path).expanduser().resolve())
    if args.as_json:
        print_json(diagnostics)
    else:
        for item in diagnostics:
            state = "available" if item["available"] else "unavailable"
            extensions = item["extensions"]
            extension_text = ",".join(str(value) for value in extensions) if isinstance(extensions, list) else str(extensions)
            print(f"{item['language']!s:<12} {extension_text:<30} {item['parser']!s:<36} {state:<12} {item['files_detected']} files  {item['status']}")
    return 0


def run_hotspots(args: argparse.Namespace) -> int:
    graph = load_graph(args.graph)
    hotspots = graph_hotspots(graph, limit=args.limit)
    if args.as_json:
        print_json(hotspots)
    elif not hotspots:
        print("No prompt or model-call hotspot detected.")
    else:
        for rank, item in enumerate(hotspots, start=1):
            location = item.get("path") or ""
            if item.get("line"):
                location += f":{item['line']}"
            print(
                f"{rank}. {item['label']} [{item['type']}] — "
                f"{item['static_tokens']} tokens — {location}"
            )
            if item.get("dynamic_inputs"):
                print(f"   Dynamic inputs: {', '.join(item['dynamic_inputs'])}")
    return 0


def run_explain(args: argparse.Namespace) -> int:
    graph = load_graph(args.graph)
    node = resolve_node(graph, args.node)
    incoming = [edge.to_dict() for edge in graph.edges if edge.target == node.id]
    outgoing = [edge.to_dict() for edge in graph.edges if edge.source == node.id]
    findings = [item.to_dict() for item in graph.findings if item.node_id == node.id]
    print_json(
        {
            "node": node.to_dict(),
            "incoming_edges": incoming,
            "outgoing_edges": outgoing,
            "findings": findings,
        }
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "build":
            return run_build(args)
        if args.command == "stats":
            return run_stats(args)
        if args.command == "languages":
            return run_languages(args)
        if args.command == "hotspots":
            return run_hotspots(args)
        if args.command == "explain":
            return run_explain(args)
        if args.command == "path":
            print_json(shortest_path(load_graph(args.graph), args.source, args.target))
            return 0
        if args.command == "query":
            print_json(query_graph(load_graph(args.graph), args.text, limit=args.limit))
            return 0

        if args.command == "count":
            count = count_tokens(read_text(args.path), backend=args.backend, model=args.model)
            if args.as_json:
                print_json(count.to_dict())
            else:
                print(f"{count.tokens} tokens ({count.backend}, {count.encoding})")
            return 0

        if args.command == "analyze":
            findings = analyze_prompt(read_text(args.path))
            if args.as_json:
                print_json([item.to_dict() for item in findings])
            elif not findings:
                print("No known token waste pattern detected.")
            else:
                for finding in findings:
                    print(f"[{finding.severity.upper()}] {finding.code}: {finding.message}")
                    print(f"  Suggestion: {finding.suggestion}")
            return 0

        if args.command == "optimize":
            prompt = read_text(args.path)
            policy = ValidationPolicy(
                min_semantic_score=args.min_semantic_score,
                required_terms=tuple(args.required_term),
            )
            report = optimize_prompt(
                prompt,
                backend=args.backend,
                model=args.model,
                policy=policy,
            )
            if args.output:
                Path(args.output).write_text(report.selected_prompt, encoding="utf-8")
            else:
                print(report.selected_prompt)
            if args.report:
                write_json_report(report, args.report)
            print(format_summary(report), file=sys.stderr)
            return 0

        if args.command == "evaluate":
            print_json(evaluate_jsonl(args.path).to_dict())
            return 0
        if args.command == "prompt-flow":
            print_json(prompt_flow(load_graph(args.graph), args.prompt))
            return 0

        if args.command == "mcp-config":
            clients = None if not args.client or "all" in args.client else args.client
            for path in write_mcp_configs(args.path, clients=clients, python=args.python):
                print(path)
            return 0

        if args.command == "agent-init":
            clients = None if not args.client or "all" in args.client else args.client
            for path in write_agent_instructions(args.path, clients=clients):
                print(path)
            return 0

        if args.command == "compare":
            original = count_tokens(read_text(args.original), backend=args.backend, model=args.model)
            optimized = count_tokens(read_text(args.optimized), backend=args.backend, model=args.model)
            saved = original.tokens - optimized.tokens
            percent = saved / original.tokens * 100 if original.tokens else 0.0
            print_json(
                {
                    "original_tokens": original.tokens,
                    "optimized_tokens": optimized.tokens,
                    "saved_tokens": saved,
                    "savings_percent": percent,
                    "backend": original.backend,
                }
            )
            return 0
    except (FileNotFoundError, KeyError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 2

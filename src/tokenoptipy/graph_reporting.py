from __future__ import annotations

import html
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from .graph_engine import compute_stats, graph_hotspots
from .graph_models import TokenGraph

TYPE_COLORS = {
    "file": "#64748b",
    "function": "#0ea5e9",
    "prompt": "#8b5cf6",
    "model_call": "#ef4444",
    "variable": "#22c55e",
    "context": "#f59e0b",
}


def json_for_inline_script(value: Any) -> str:
    """Serialize JSON without allowing project text to terminate the script element."""
    return (
        json.dumps(value, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def write_graph_json(graph: TokenGraph, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(graph.to_dict(), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return output


def markdown_report(graph: TokenGraph) -> str:
    stats = compute_stats(graph)
    hotspots = graph_hotspots(graph, limit=10)
    severity_counts = Counter(finding.severity for finding in graph.findings)
    lines = [
        "# TokenOptiPy TokenGraph Report",
        "",
        f"Project: `{graph.project_root}`",
        "",
        "## Summary",
        "",
        f"- Files scanned: **{graph.metadata.get('file_count', 0)}**",
        f"- Graph nodes: **{stats['node_count']}**",
        f"- Graph edges: **{stats['edge_count']}**",
        f"- Prompts detected: **{stats['prompt_count']}**",
        f"- Estimated static prompt tokens: **{stats['total_static_prompt_tokens']}**",
        f"- Findings: **{stats['finding_count']}**",
        "",
        "## Findings by severity",
        "",
    ]
    if severity_counts:
        for severity, count in sorted(severity_counts.items()):
            lines.append(f"- {severity}: **{count}**")
    else:
        lines.append("No known issue detected.")

    lines.extend(["", "## Token hotspots", ""])
    if hotspots:
        lines.append("| Rank | Type | Node | Tokens | Location |")
        lines.append("|---:|---|---|---:|---|")
        for rank, item in enumerate(hotspots, start=1):
            location = item.get("path") or ""
            if item.get("line"):
                location += f":{item['line']}"
            lines.append(
                f"| {rank} | {item['type']} | `{item['label']}` | "
                f"{item['static_tokens']} | `{location}` |"
            )
    else:
        lines.append("No prompt or model-call hotspot detected.")

    lines.extend(["", "## Recommendations", ""])
    if graph.findings:
        for finding in sorted(
            graph.findings,
            key=lambda item: item.estimated_saving_tokens,
            reverse=True,
        ):
            node = graph.nodes.get(finding.node_id)
            label = node.label if node else finding.node_id
            lines.extend(
                [
                    f"### {finding.code} — {label}",
                    "",
                    f"- Severity: **{finding.severity}**",
                    f"- Confidence: **{finding.confidence:.0%}**",
                    f"- Estimated potential saving: **{finding.estimated_saving_tokens} tokens**",
                    f"- Observation: {finding.message}",
                    f"- Recommendation: {finding.suggestion}",
                    "",
                ]
            )
    else:
        lines.append("No recommendation generated.")

    lines.extend(
        [
            "## Interpretation",
            "",
            "Token counts are local estimates unless a model-specific tokenizer is selected. "
            "Dynamic context sizes are unknown until runtime and should be measured in production.",
            "",
            "TokenOptiPy does not send source code or prompts to an external AI service.",
            "",
        ]
    )
    return "\n".join(lines)


def write_markdown_report(graph: TokenGraph, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown_report(graph), encoding="utf-8")
    return output


def graph_html(graph: TokenGraph) -> str:
    nodes = list(graph.nodes.values())
    edges = graph.edges
    width = 1400
    height = max(800, 500 + len(nodes) * 3)
    center_x = width * 0.46
    center_y = height * 0.5
    radius = min(width, height) * 0.36
    ordered = sorted(nodes, key=lambda node: (node.type, node.label))
    positions: dict[str, tuple[float, float]] = {}
    count = max(1, len(ordered))
    for index, node in enumerate(ordered):
        angle = 2 * math.pi * index / count
        layer = 0.72 + (index % 4) * 0.08
        positions[node.id] = (
            center_x + radius * layer * math.cos(angle),
            center_y + radius * layer * math.sin(angle),
        )

    edge_svg = []
    for edge in edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        x1, y1 = positions[edge.source]
        x2, y2 = positions[edge.target]
        edge_svg.append(
            f'<line class="edge edge-{html.escape(edge.type)}" '
            f'x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'data-type="{html.escape(edge.type)}"><title>{html.escape(edge.type)}</title></line>'
        )

    node_svg = []
    node_payload: dict[str, Any] = {}
    max_tokens = max([node.static_tokens for node in nodes] or [1])
    for node in ordered:
        x, y = positions[node.id]
        size = 7 + 17 * math.sqrt(node.static_tokens / max_tokens) if node.static_tokens else 7
        color = TYPE_COLORS.get(node.type, "#334155")
        label = node.label if len(node.label) <= 22 else node.label[:21] + "…"
        node_svg.append(
            f'<g class="node node-{html.escape(node.type)}" data-id="{html.escape(node.id)}" '
            f'data-type="{html.escape(node.type)}" tabindex="0">'
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{size:.2f}" fill="{color}"></circle>'
            f'<text x="{x + size + 4:.2f}" y="{y + 4:.2f}">{html.escape(label)}</text>'
            "</g>"
        )
        node_payload[node.id] = node.to_dict()

    findings_payload = [finding.to_dict() for finding in graph.findings]
    legend = "".join(
        f'<label><input type="checkbox" data-filter="{node_type}" checked> '
        f'<span style="color:{color}">●</span> {node_type}</label>'
        for node_type, color in TYPE_COLORS.items()
    )
    stats = compute_stats(graph)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TokenOptiPy TokenGraph</title>
<style>
:root {{ color-scheme: light dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
body {{ margin:0; background:#0f172a; color:#e2e8f0; }}
header {{ padding:18px 24px; display:flex; gap:22px; align-items:center; border-bottom:1px solid #334155; }}
h1 {{ margin:0; font-size:22px; }}
.summary {{ color:#94a3b8; }}
.controls {{ padding:12px 24px; display:flex; gap:16px; flex-wrap:wrap; border-bottom:1px solid #334155; }}
.controls input[type=search] {{ width:320px; padding:8px 10px; border-radius:8px; border:1px solid #475569; background:#111827; color:#fff; }}
.controls label {{ font-size:13px; }}
main {{ display:grid; grid-template-columns:minmax(0,1fr) 360px; height:calc(100vh - 124px); }}
.graph {{ overflow:auto; background:radial-gradient(circle at center,#172554,#0f172a 55%); }}
svg {{ min-width:{width}px; min-height:{height}px; }}
.edge {{ stroke:#475569; stroke-width:1.2; opacity:.55; }}
.node {{ cursor:pointer; }}
.node circle {{ stroke:#e2e8f0; stroke-width:1; }}
.node text {{ fill:#e2e8f0; font-size:10px; pointer-events:none; }}
.node.hidden, .edge.hidden {{ display:none; }}
.node.match circle {{ stroke:#facc15; stroke-width:4; }}
aside {{ border-left:1px solid #334155; padding:18px; overflow:auto; background:#111827; }}
pre {{ white-space:pre-wrap; word-break:break-word; font-size:12px; }}
.finding {{ border:1px solid #334155; border-radius:8px; padding:10px; margin:10px 0; }}
.badge {{ display:inline-block; border-radius:999px; padding:2px 8px; background:#334155; font-size:11px; }}
</style>
</head>
<body>
<header>
  <h1>TokenOptiPy TokenGraph</h1>
  <div class="summary">{stats['node_count']} nodes · {stats['edge_count']} edges · {stats['total_static_prompt_tokens']} static prompt tokens</div>
</header>
<div class="controls">
  <input id="search" type="search" placeholder="Search node, file, prompt…">
  {legend}
</div>
<main>
<section class="graph">
<svg viewBox="0 0 {width} {height}" role="img" aria-label="Token graph">
{''.join(edge_svg)}
{''.join(node_svg)}
</svg>
</section>
<aside>
<h2>Node details</h2>
<p>Select a node in the graph.</p>
<div id="details"></div>
<h2>Findings</h2>
<div id="findings"></div>
</aside>
</main>
<script>
const nodes = {json_for_inline_script(node_payload)};
const findings = {json_for_inline_script(findings_payload)};
const details = document.getElementById('details');
const findingsBox = document.getElementById('findings');
function renderNode(id) {{
  const node = nodes[id];
  if (!node) return;
  details.innerHTML = `<h3>${{escapeHtml(node.label)}}</h3>
  <p><span class="badge">${{escapeHtml(node.type)}}</span> ${{node.static_tokens || 0}} tokens</p>
  <pre>${{escapeHtml(JSON.stringify(node, null, 2))}}</pre>`;
  const local = findings.filter(item => item.node_id === id);
  findingsBox.innerHTML = local.length ? local.map(item => `<div class="finding"><b>${{escapeHtml(item.code)}}</b> · ${{escapeHtml(item.severity)}}<p>${{escapeHtml(item.message)}}</p><p>${{escapeHtml(item.suggestion)}}</p></div>`).join('') : '<p>No finding for this node.</p>';
}}
function escapeHtml(value) {{
  return String(value).replace(/[&<>'"]/g, char => ({{'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}})[char]);
}}
document.querySelectorAll('.node').forEach(element => {{
  element.addEventListener('click', () => renderNode(element.dataset.id));
  element.addEventListener('keydown', event => {{ if (event.key === 'Enter') renderNode(element.dataset.id); }});
}});
document.querySelectorAll('input[data-filter]').forEach(input => {{
  input.addEventListener('change', () => {{
    const type = input.dataset.filter;
    document.querySelectorAll(`.node-${{CSS.escape(type)}}`).forEach(node => node.classList.toggle('hidden', !input.checked));
  }});
}});
document.getElementById('search').addEventListener('input', event => {{
  const query = event.target.value.trim().toLowerCase();
  document.querySelectorAll('.node').forEach(element => {{
    const node = nodes[element.dataset.id];
    const haystack = `${{node.id}} ${{node.label}} ${{node.path || ''}} ${{node.type}}`.toLowerCase();
    element.classList.toggle('match', Boolean(query) && haystack.includes(query));
  }});
}});
findingsBox.innerHTML = findings.slice(0, 20).map(item => `<div class="finding"><b>${{escapeHtml(item.code)}}</b> · ${{escapeHtml(item.severity)}}<p>${{escapeHtml(item.message)}}</p></div>`).join('') || '<p>No finding.</p>';
</script>
</body>
</html>"""


def write_graph_html(graph: TokenGraph, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(graph_html(graph), encoding="utf-8")
    return output


def write_graph_outputs(graph: TokenGraph, output_dir: str | Path) -> dict[str, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return {
        "json": write_graph_json(graph, directory / "graph.json"),
        "markdown": write_markdown_report(graph, directory / "TOKEN_REPORT.md"),
        "html": write_graph_html(graph, directory / "graph.html"),
    }

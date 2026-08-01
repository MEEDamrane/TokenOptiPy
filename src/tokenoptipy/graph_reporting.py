from __future__ import annotations

import json
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
        json.dumps(graph.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return output


def markdown_report(graph: TokenGraph) -> str:
    stats, hotspots = compute_stats(graph), graph_hotspots(graph, limit=10)
    severities = Counter(item.severity for item in graph.findings)
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
    lines.extend(
        [f"- {key}: **{value}**" for key, value in sorted(severities.items())]
        or ["No known issue detected."]
    )
    lines += [
        "",
        "## Token hotspots",
        "",
        "| Rank | Type | Node | Tokens | Location |",
        "|---:|---|---|---:|---|",
    ]
    for rank, item in enumerate(hotspots, 1):
        location = item.get("path") or ""
        if item.get("line"):
            location += f":{item['line']}"
        lines.append(
            f"| {rank} | {item['type']} | `{item['label']}` | {item['static_tokens']} | `{location}` |"
        )
    lines += ["", "## Recommendations", ""]
    for finding in sorted(
        graph.findings, key=lambda item: item.estimated_saving_tokens, reverse=True
    ):
        node = graph.nodes.get(finding.node_id)
        lines += [
            f"### {finding.code} — {node.label if node else finding.node_id}",
            "",
            f"- Severity: **{finding.severity}**",
            f"- Confidence: **{finding.confidence:.0%}**",
            f"- Estimated potential saving: **{finding.estimated_saving_tokens} tokens**",
            f"- Observation: {finding.message}",
            f"- Recommendation: {finding.suggestion}",
            "",
        ]
    lines += [
        "## Interpretation",
        "",
        "Token counts are local estimates. Dynamic context sizes remain unknown until runtime.",
        "",
        "TokenOptiPy does not send source code or prompts to an external service.",
        "",
    ]
    return "\n".join(lines)


def write_markdown_report(graph: TokenGraph, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown_report(graph), encoding="utf-8")
    return output


def graph_html(graph: TokenGraph) -> str:
    data, stats, colors = (
        json_for_inline_script(graph.to_dict()),
        compute_stats(graph),
        json_for_inline_script(TYPE_COLORS),
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TokenOptiPy TokenGraph</title><style>
:root{{color-scheme:light;--bg:#f4f7fb;--panel:#fff;--ink:#172033;--muted:#667085;--line:#d9e0ea;--accent:#6d5dfc;--graph:#edf2fa;font-family:Inter,"Segoe UI",sans-serif}}:root[data-theme=dark]{{color-scheme:dark;--bg:#0b1020;--panel:#121a2d;--ink:#ecf1ff;--muted:#98a4bd;--line:#293550;--accent:#9488ff;--graph:#0e1629}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink)}}button,input,select{{font:inherit;color:inherit}}header{{padding:18px 22px;display:flex;justify-content:space-between;align-items:center}}h1{{margin:0;font-size:22px}}.sub{{color:var(--muted);font-size:12px}}button,.control{{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:8px 10px}}button{{cursor:pointer}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:0 22px 14px}}.stat{{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:12px}}.stat b{{display:block;font-size:21px}}.stat span{{color:var(--muted);font-size:12px}}.toolbar{{display:flex;gap:8px;padding:0 22px 14px;flex-wrap:wrap}}#search{{min-width:270px}}main{{height:calc(100vh - 190px);display:grid;grid-template-columns:250px minmax(360px,1fr) 350px;gap:1px;background:var(--line);border-top:1px solid var(--line)}}aside,.canvas{{background:var(--panel);overflow:auto}}aside{{padding:14px}}aside h2{{font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}}.canvas{{position:relative;background:var(--graph);overflow:hidden;cursor:grab}}svg{{width:100%;height:100%}}.edge{{fill:none;stroke:#71809b;stroke-width:1.5;opacity:.55;marker-end:url(#arrow)}}.edge.focus{{stroke:var(--accent);stroke-width:3;opacity:1}}.node{{cursor:pointer}}.node circle{{stroke:var(--panel);stroke-width:2}}.node text{{fill:var(--ink);font-size:11px;paint-order:stroke;stroke:var(--graph);stroke-width:4px}}.node.dim,.edge.dim{{opacity:.08}}.node.match circle{{stroke:#f5b700;stroke-width:5}}.item{{border:1px solid var(--line);border-radius:9px;padding:9px;margin:7px 0;cursor:pointer;word-break:break-word}}.badge{{display:inline-block;color:var(--accent);border-radius:99px;padding:2px 7px;background:color-mix(in srgb,var(--accent) 15%,transparent);font:11px "JetBrains Mono","Cascadia Code",monospace}}dl{{display:grid;grid-template-columns:105px 1fr;gap:7px;font-size:12px}}dt{{color:var(--muted)}}dd{{margin:0;word-break:break-word}}.filters label{{display:block;font-size:12px;margin:6px 0}}@media(max-width:900px){{main{{grid-template-columns:190px 1fr}}#inspector{{display:none}}.stats{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><header><div><h1>TokenGraph</h1><div class="sub">TokenOptiPy 0.3.0 · local, privacy-safe report</div></div><button id="theme">Light / dark</button></header><section class="stats"><div class="stat"><b>{stats["node_count"]}</b><span>Nodes</span></div><div class="stat"><b>{stats["edge_count"]}</b><span>Edges</span></div><div class="stat"><b>{stats["prompt_count"]}</b><span>Prompts</span></div><div class="stat"><b>{stats["total_static_prompt_tokens"]}</b><span>Prompt tokens</span></div></section><div class="toolbar"><input class="control" id="search" type="search" placeholder="Search nodes, paths, IDs…"><select class="control" id="edgeFilter"><option value="">All relations</option></select><button id="reset">Reset view</button><button id="clear">Clear focus</button></div><main><aside><h2>Node filters</h2><div class="filters" id="nodeFilters"></div><h2>Prompts</h2><div id="prompts"></div></aside><section class="canvas"><svg id="graph" viewBox="0 0 1400 900"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="#71809b"/></marker></defs><g id="viewport"></g></svg></section><aside id="inspector"><h2>Inspector</h2><p class="sub">Select a node or prompt to inspect its directed flow.</p><div id="details"></div></aside></main><script>
const data={data},colors={colors},byId=Object.fromEntries(data.nodes.map(n=>[n.id,n])),viewport=document.getElementById('viewport'),NS='http://www.w3.org/2000/svg';const el=(n,a={{}},t='')=>{{const x=document.createElementNS(NS,n);Object.entries(a).forEach(([k,v])=>x.setAttribute(k,String(v)));if(t)x.textContent=t;return x}},pos={{}},count=Math.max(data.nodes.length,1);data.nodes.forEach((n,i)=>{{const a=2*Math.PI*i/count,r=270+(i%4)*55;pos[n.id]=[700+r*Math.cos(a),450+r*.72*Math.sin(a)]}});data.edges.forEach((e,i)=>{{if(!pos[e.source]||!pos[e.target])return;const [x1,y1]=pos[e.source],[x2,y2]=pos[e.target],p=el('path',{{d:`M${{x1}},${{y1}} Q${{(x1+x2)/2}},${{(y1+y2)/2-35-(i%3)*12}} ${{x2}},${{y2}}`,class:'edge','data-source':e.source,'data-target':e.target,'data-type':e.type}});p.append(el('title',{{}},e.type));viewport.append(p)}});data.nodes.forEach(n=>{{const [x,y]=pos[n.id],g=el('g',{{class:'node','data-id':n.id,'data-type':n.type,tabindex:0}}),r=8+Math.min(18,Math.sqrt(n.static_tokens||0));g.append(el('circle',{{cx:x,cy:y,r,fill:colors[n.type]||'#64748b'}}),el('text',{{x:x+r+5,y:y+4}},n.label.length>28?n.label.slice(0,27)+'…':n.label));g.onclick=()=>select(n.id,n.type==='prompt');g.onkeydown=e=>e.key==='Enter'&&select(n.id,n.type==='prompt');viewport.append(g)}});const types=[...new Set(data.nodes.map(n=>n.type))].sort(),relations=[...new Set(data.edges.map(e=>e.type))].sort();types.forEach(t=>{{const l=document.createElement('label'),c=document.createElement('input');c.type='checkbox';c.checked=true;c.dataset.type=t;c.onchange=filters;l.append(c,document.createTextNode(' '+t));nodeFilters.append(l)}});relations.forEach(t=>{{const o=document.createElement('option');o.value=t;o.textContent=t;edgeFilter.append(o)}});data.nodes.filter(n=>n.type==='prompt').sort((a,b)=>b.static_tokens-a.static_tokens).forEach(n=>{{const d=document.createElement('div'),b=document.createElement('span');d.className='item';b.className='badge';b.textContent=n.static_tokens+' tokens';d.append(b,document.createElement('br'),document.createTextNode(n.label));d.onclick=()=>select(n.id,true);prompts.append(d)}});
function neighbors(id){{const s=new Set([id]);data.edges.forEach(e=>{{if(e.source===id||e.target===id){{s.add(e.source);s.add(e.target)}}}});return s}}function select(id,focus=false){{const n=byId[id],ids=focus?neighbors(id):new Set(data.nodes.map(x=>x.id));document.querySelectorAll('.node').forEach(x=>x.classList.toggle('dim',!ids.has(x.dataset.id)));document.querySelectorAll('.edge').forEach(x=>{{const on=ids.has(x.dataset.source)&&ids.has(x.dataset.target);x.classList.toggle('dim',!on);x.classList.toggle('focus',focus&&on)}});const inc=data.edges.filter(e=>e.target===id),out=data.edges.filter(e=>e.source===id),calls=[...ids].map(x=>byId[x]).filter(x=>x?.type==='model_call'),tokens=[...ids].reduce((s,x)=>s+(byId[x]?.static_tokens||0),0),find=data.findings.filter(f=>ids.has(f.node_id));details.replaceChildren();const h=document.createElement('h3'),badge=document.createElement('span'),dl=document.createElement('dl');h.textContent=n.label;badge.className='badge';badge.textContent=n.type;[['Node ID',n.id],['Path',n.path||'—'],['Prompt tokens',n.static_tokens||0],['Flow tokens',tokens],['Incoming',inc.map(e=>e.type).join(', ')||'—'],['Outgoing',out.map(e=>e.type).join(', ')||'—'],['Connected nodes',ids.size-1],['Model calls',calls.map(x=>x.label).join(', ')||'—'],['Findings',find.map(x=>x.code).join(', ')||'—'],['Trace ID',data.metadata.trace_id||'generated report']].forEach(([a,b])=>{{const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=a;dd.textContent=String(b);dl.append(dt,dd)}});details.append(h,badge,dl)}}function filters(){{const enabled=new Set([...document.querySelectorAll('#nodeFilters input:checked')].map(x=>x.dataset.type));document.querySelectorAll('.node').forEach(x=>x.style.display=enabled.has(x.dataset.type)?'':'none');document.querySelectorAll('.edge').forEach(x=>x.style.display=(!edgeFilter.value||x.dataset.type===edgeFilter.value)?'':'none')}}edgeFilter.onchange=filters;search.oninput=()=>{{const q=search.value.toLowerCase();document.querySelectorAll('.node').forEach(x=>{{const n=byId[x.dataset.id];x.classList.toggle('match',!!q&&`${{n.id}} ${{n.label}} ${{n.path||''}} ${{n.type}}`.toLowerCase().includes(q))}})}};let scale=1,tx=0,ty=0,drag=false,last=[0,0];function transform(){{viewport.setAttribute('transform',`translate(${{tx}} ${{ty}}) scale(${{scale}})`)}}graph.onwheel=e=>{{e.preventDefault();scale=Math.max(.25,Math.min(4,scale*(e.deltaY<0?1.1:.9)));transform()}};graph.onpointerdown=e=>{{drag=true;last=[e.clientX,e.clientY];graph.setPointerCapture(e.pointerId)}};graph.onpointermove=e=>{{if(drag){{tx+=e.clientX-last[0];ty+=e.clientY-last[1];last=[e.clientX,e.clientY];transform()}}}};graph.onpointerup=()=>drag=false;reset.onclick=()=>{{scale=1;tx=ty=0;transform()}};clear.onclick=()=>{{document.querySelectorAll('.dim,.focus').forEach(x=>x.classList.remove('dim','focus'));details.replaceChildren()}};theme.onclick=()=>document.documentElement.dataset.theme=document.documentElement.dataset.theme==='dark'?'':'dark';
</script></body></html>"""


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

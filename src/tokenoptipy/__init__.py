"""TokenOptiPy: local token-flow graphs and safe prompt optimization."""

from .analyzer import analyze_prompt
from .counters import count_tokens, resolve_counter
from .graph_engine import build_token_graph, graph_hotspots, load_graph, query_graph
from .graph_models import GraphEdge, GraphFinding, GraphNode, TokenGraph
from .optimizer import optimize_prompt
from .validators import ValidationPolicy, validate_candidate

__all__ = [
    "GraphEdge",
    "GraphFinding",
    "GraphNode",
    "TokenGraph",
    "ValidationPolicy",
    "analyze_prompt",
    "build_token_graph",
    "count_tokens",
    "graph_hotspots",
    "load_graph",
    "optimize_prompt",
    "query_graph",
    "resolve_counter",
    "validate_candidate",
]

__version__ = "0.5.0"

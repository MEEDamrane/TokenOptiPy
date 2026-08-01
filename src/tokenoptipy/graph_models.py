from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class GraphNode:
    id: str
    type: str
    label: str
    path: str | None = None
    line: int | None = None
    end_line: int | None = None
    static_tokens: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphNode:
        return cls(**data)


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    type: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphEdge:
        return cls(**data)


@dataclass(frozen=True)
class GraphFinding:
    code: str
    severity: str
    node_id: str
    message: str
    suggestion: str
    estimated_saving_tokens: int = 0
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphFinding:
        return cls(**data)


@dataclass
class TokenGraph:
    project_root: str
    version: str = "0.4"
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    findings: list[GraphFinding] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    _edge_keys: set[tuple[str, str, str]] = field(default_factory=set, init=False, repr=False)
    _finding_keys: set[tuple[str, str, str]] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        self._edge_keys.update((edge.source, edge.target, edge.type) for edge in self.edges)
        self._finding_keys.update(
            (item.code, item.node_id, item.message) for item in self.findings
        )

    def add_node(self, node: GraphNode) -> None:
        existing = self.nodes.get(node.id)
        if existing is None or node.static_tokens >= existing.static_tokens:
            self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        key = (edge.source, edge.target, edge.type)
        if key not in self._edge_keys:
            self.edges.append(edge)
            self._edge_keys.add(key)

    def add_finding(self, finding: GraphFinding) -> None:
        key = (finding.code, finding.node_id, finding.message)
        if key not in self._finding_keys:
            self.findings.append(finding)
            self._finding_keys.add(key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "project_root": self.project_root,
            "metadata": self.metadata,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
            "findings": [finding.to_dict() for finding in self.findings],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenGraph:
        graph = cls(
            project_root=data.get("project_root", "."),
            version=data.get("version", "0.4"),
            metadata=data.get("metadata", {}),
        )
        for node_data in data.get("nodes", []):
            graph.add_node(GraphNode.from_dict(node_data))
        for edge_data in data.get("edges", []):
            graph.add_edge(GraphEdge.from_dict(edge_data))
        for finding_data in data.get("findings", []):
            graph.add_finding(GraphFinding.from_dict(finding_data))
        return graph

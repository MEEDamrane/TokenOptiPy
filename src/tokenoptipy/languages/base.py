from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from tokenoptipy.graph_models import GraphEdge, GraphNode


@dataclass(frozen=True)
class ParsedFile:
    path: Path
    relative_path: str
    source: str
    language: str
    parser: str


@dataclass(frozen=True)
class PromptCandidate:
    name: str
    text: str
    start_line: int
    end_line: int
    confidence: float = 0.8
    reasons: tuple[str, ...] = ()
    dynamic_parts: tuple[str, ...] = ()


@dataclass(frozen=True)
class VariableCandidate:
    name: str
    line: int


@dataclass(frozen=True)
class FunctionCandidate:
    name: str
    line: int


@dataclass(frozen=True)
class ImportCandidate:
    value: str
    line: int
    local: bool = False


@dataclass(frozen=True)
class ModelCallCandidate:
    name: str
    line: int
    confidence: float
    reasons: tuple[str, ...]
    arguments: tuple[str, ...] = ()


@dataclass(frozen=True)
class FlowCandidate:
    source: str
    target: str
    relation: str = "FLOWS_TO"


@dataclass
class LanguageExtraction:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    imports: list[ImportCandidate] = field(default_factory=list)


class LanguageAdapter(Protocol):
    language_id: str
    extensions: tuple[str, ...]
    parser_name: str
    experimental: bool

    def is_available(self) -> bool: ...
    def unavailable_reason(self) -> str | None: ...
    def detect_project(self, root: Path) -> bool: ...
    def parse_file(self, path: Path, content: bytes, relative_path: str = "") -> ParsedFile: ...
    def extract_prompts(self, parsed: ParsedFile) -> list[PromptCandidate]: ...
    def extract_variables(self, parsed: ParsedFile) -> list[VariableCandidate]: ...
    def extract_functions(self, parsed: ParsedFile) -> list[FunctionCandidate]: ...
    def extract_imports(self, parsed: ParsedFile) -> list[ImportCandidate]: ...
    def extract_model_calls(self, parsed: ParsedFile) -> list[ModelCallCandidate]: ...
    def extract_flows(self, parsed: ParsedFile) -> list[FlowCandidate]: ...
    def extract(self, parsed: ParsedFile, backend: str = "simple") -> LanguageExtraction: ...

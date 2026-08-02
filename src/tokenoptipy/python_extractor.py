from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .counters import count_tokens
from .graph_models import GraphEdge, GraphNode
from .privacy import compact_preview, redact_preview

PROMPT_NAME_RE = re.compile(
    r"(?:prompt|instruction|system|message|context|template|schema|history|conversation)",
    re.IGNORECASE,
)
MODEL_CALL_NAMES = {
    "chat",
    "complete",
    "completion",
    "completions",
    "create",
    "generate",
    "invoke",
    "predict",
    "respond",
    "run",
}
PROMPT_KEYWORDS = {
    "prompt",
    "messages",
    "input",
    "system",
    "instruction",
    "context",
    "schema",
}


@dataclass
class PythonExtraction:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    variable_nodes: dict[str, str] = field(default_factory=dict)
    function_nodes: dict[str, str] = field(default_factory=dict)


def stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{digest}"


def preview_text(text: str, limit: int = 180) -> str:
    return compact_preview(text, limit=limit)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()




def term_hashes(text: str) -> list[int]:
    terms = set(re.findall(r"[\w'-]+", text.lower(), flags=re.UNICODE))
    return sorted(
        int.from_bytes(
            hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest(),
            "big",
        )
        for term in terms
    )

def minhash_signature(text: str, size: int = 32) -> list[int]:
    terms = set(re.findall(r"[\w'-]+", text.lower(), flags=re.UNICODE))
    if not terms:
        return [0] * size
    signature: list[int] = []
    for index in range(size):
        minimum = min(
            int.from_bytes(
                hashlib.blake2b(
                    f"{index}:{term}".encode(),
                    digest_size=8,
                ).digest(),
                "big",
            )
            for term in terms
        )
        signature.append(minimum)
    return signature


def joined_string_text(node: ast.JoinedStr) -> tuple[str, list[str]]:
    chunks: list[str] = []
    variables: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            chunks.append(value.value)
        elif isinstance(value, ast.FormattedValue):
            expression = ast.unparse(value.value)
            chunks.append("{" + expression + "}")
            variables.append(expression)
    return "".join(chunks), variables


def literal_read_path(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    if node.func.attr not in {"read_text", "read_bytes"}:
        return None
    owner = node.func.value
    if not isinstance(owner, ast.Call):
        return None
    owner_name = PythonProjectVisitor._call_name(owner.func) if "PythonProjectVisitor" in globals() else ""
    if owner_name.rsplit(".", 1)[-1] not in {"Path", "PurePath"}:
        return None
    if not owner.args:
        return None
    path_value = owner.args[0]
    if isinstance(path_value, ast.Constant) and isinstance(path_value.value, str):
        return path_value.value
    return None


def expression_text(node: ast.AST) -> tuple[str | None, list[str]]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, []
    if isinstance(node, ast.JoinedStr):
        return joined_string_text(node)
    if isinstance(node, (ast.List, ast.Tuple)):
        values: list[str] = []
        variables: list[str] = []
        for element in node.elts:
            text, refs = expression_text(element)
            if text:
                values.append(text)
            variables.extend(refs)
        return "\n".join(values) if values else None, variables
    if isinstance(node, ast.Dict):
        values = []
        variables = []
        for key, value in zip(node.keys, node.values, strict=False):
            key_text = ast.unparse(key) if key is not None else ""
            text, refs = expression_text(value)
            if text:
                values.append(f"{key_text}: {text}")
            variables.extend(refs)
        return "\n".join(values) if values else None, variables
    return None, []


def is_prompt_candidate(name: str, text: str) -> bool:
    if text.lstrip().lower().startswith(("<!doctype html", "<html")):
        return False
    if PROMPT_NAME_RE.search(name):
        return True
    lowered = text.lower()
    prompt_markers = (
        "you are ",
        "return only",
        "respond with",
        "assistant",
        "system message",
        "instructions:",
        "réponds",
        "analyse",
    )
    return len(text) >= 100 and any(marker in lowered for marker in prompt_markers)


class PythonProjectVisitor(ast.NodeVisitor):
    def __init__(self, relative_path: str, backend: str = "simple") -> None:
        self.relative_path = relative_path
        self.backend = backend
        self.extraction = PythonExtraction()
        self.scope: list[str] = []
        self.current_function: str | None = None
        self.known_assignments: dict[str, str] = {}
        self.file_node_id = f"file:{relative_path}"

    def qualified_name(self, name: str) -> str:
        return ".".join([*self.scope, name]) if self.scope else name

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        qualified = self.qualified_name(node.name)
        node_id = stable_id("function", self.relative_path, qualified)
        self.extraction.function_nodes[qualified] = node_id
        self.extraction.nodes.append(
            GraphNode(
                id=node_id,
                type="function",
                label=qualified,
                path=self.relative_path,
                line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                attributes={"root_file": self.relative_path},
            )
        )
        self.extraction.edges.append(
            GraphEdge(self.file_node_id, node_id, "DEFINES")
        )
        previous = self.current_function
        self.current_function = node_id
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()
        self.current_function = previous
        return node

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Assign(self, node: ast.Assign) -> Any:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._record_assignment(target.id, node.value, node)
        self.generic_visit(node)
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        if isinstance(node.target, ast.Name) and node.value is not None:
            self._record_assignment(node.target.id, node.value, node)
        self.generic_visit(node)
        return node

    def _record_assignment(self, name: str, value: ast.AST, node: ast.AST) -> None:
        loaded_path = literal_read_path(value)
        if loaded_path and PROMPT_NAME_RE.search(name):
            qualified = self.qualified_name(name)
            node_id = stable_id(
                "variable", self.relative_path, qualified, str(getattr(node, "lineno", 0))
            )
            self.known_assignments[name] = node_id
            self.extraction.variable_nodes[qualified] = node_id
            self.extraction.variable_nodes[name] = node_id
            self.extraction.nodes.append(
                GraphNode(
                    id=node_id,
                    type="variable",
                    label=qualified,
                    path=self.relative_path,
                    line=getattr(node, "lineno", None),
                    end_line=getattr(node, "end_lineno", None),
                    attributes={
                        "root_file": self.relative_path,
                        "source_kind": "file_prompt_reference",
                        "loaded_path": loaded_path,
                        "dynamic": False,
                    },
                )
            )
            parent = self.current_function or self.file_node_id
            self.extraction.edges.append(GraphEdge(parent, node_id, "DEFINES_VARIABLE"))
            return

        text, variables = expression_text(value)
        if text is None or not is_prompt_candidate(name, text):
            return

        qualified = self.qualified_name(name)
        node_id = stable_id(
            "prompt", self.relative_path, qualified, str(getattr(node, "lineno", 0))
        )
        count = count_tokens(text, backend=self.backend)
        preview, has_secret = redact_preview(text)
        self.known_assignments[name] = node_id
        self.extraction.variable_nodes[qualified] = node_id
        self.extraction.variable_nodes[name] = node_id
        self.extraction.nodes.append(
            GraphNode(
                id=node_id,
                type="prompt",
                label=qualified,
                path=self.relative_path,
                line=getattr(node, "lineno", None),
                end_line=getattr(node, "end_lineno", None),
                static_tokens=count.tokens,
                attributes={
                    "root_file": self.relative_path,
                    "source_kind": "python_assignment",
                    "preview": preview,
                    "content_hash": content_hash(text),
                    "minhash": minhash_signature(text),
                    "term_hashes": term_hashes(text),
                    "characters": len(text),
                    "placeholders": sorted(set(variables)),
                    "has_possible_secret": has_secret,
                },
            )
        )
        parent = self.current_function or self.file_node_id
        self.extraction.edges.append(GraphEdge(parent, node_id, "DEFINES_PROMPT"))
        for variable in variables:
            known_id = self.known_assignments.get(variable)
            if known_id:
                self.extraction.edges.append(GraphEdge(known_id, node_id, "INCLUDES"))
                continue
            variable_id = stable_id("variable", self.relative_path, variable)
            self.extraction.nodes.append(
                GraphNode(
                    id=variable_id,
                    type="variable",
                    label=variable,
                    path=self.relative_path,
                    line=getattr(node, "lineno", None),
                    attributes={"root_file": self.relative_path, "dynamic": True},
                )
            )
            self.extraction.edges.append(GraphEdge(node_id, variable_id, "USES_VARIABLE"))

    def visit_Call(self, node: ast.Call) -> Any:
        call_name = self._call_name(node.func)
        terminal = call_name.rsplit(".", 1)[-1].lower()
        is_model_call = terminal in MODEL_CALL_NAMES and (
            any(keyword.arg in PROMPT_KEYWORDS for keyword in node.keywords if keyword.arg)
            or "chat" in call_name.lower()
            or "llm" in call_name.lower()
            or "model" in call_name.lower()
            or "completion" in call_name.lower()
        )

        if is_model_call:
            call_id = stable_id(
                "model_call",
                self.relative_path,
                call_name,
                str(getattr(node, "lineno", 0)),
            )
            self.extraction.nodes.append(
                GraphNode(
                    id=call_id,
                    type="model_call",
                    label=call_name,
                    path=self.relative_path,
                    line=getattr(node, "lineno", None),
                    end_line=getattr(node, "end_lineno", None),
                    attributes={"root_file": self.relative_path},
                )
            )
            parent = self.current_function or self.file_node_id
            self.extraction.edges.append(GraphEdge(parent, call_id, "CALLS_MODEL"))
            self._link_call_inputs(node, call_id)

        self.generic_visit(node)
        return node

    def _link_call_inputs(self, node: ast.Call, call_id: str) -> None:
        candidates: list[tuple[str, ast.AST]] = []
        for keyword in node.keywords:
            if keyword.arg in PROMPT_KEYWORDS:
                candidates.append((keyword.arg or "input", keyword.value))
        if not candidates and node.args:
            candidates.append(("positional_input", node.args[0]))

        for role, expression in candidates:
            if isinstance(expression, ast.Name):
                prompt_id = self.known_assignments.get(expression.id)
                if prompt_id:
                    self.extraction.edges.append(
                        GraphEdge(prompt_id, call_id, "FLOWS_TO", {"role": role})
                    )
                else:
                    variable_id = stable_id("variable", self.relative_path, expression.id)
                    self.extraction.nodes.append(
                        GraphNode(
                            id=variable_id,
                            type="context",
                            label=expression.id,
                            path=self.relative_path,
                            line=getattr(expression, "lineno", None),
                            attributes={
                                "root_file": self.relative_path,
                                "dynamic": True,
                                "role": role,
                            },
                        )
                    )
                    self.extraction.edges.append(
                        GraphEdge(variable_id, call_id, "FLOWS_TO", {"role": role})
                    )
                continue

            text, variables = expression_text(expression)
            if text:
                prompt_id = stable_id(
                    "prompt",
                    self.relative_path,
                    "inline",
                    str(getattr(expression, "lineno", 0)),
                    role,
                )
                count = count_tokens(text, backend=self.backend)
                preview, has_secret = redact_preview(text)
                self.extraction.nodes.append(
                    GraphNode(
                        id=prompt_id,
                        type="prompt",
                        label=f"inline {role}",
                        path=self.relative_path,
                        line=getattr(expression, "lineno", None),
                        end_line=getattr(expression, "end_lineno", None),
                        static_tokens=count.tokens,
                        attributes={
                            "root_file": self.relative_path,
                            "source_kind": "python_inline_call",
                            "preview": preview,
                            "content_hash": content_hash(text),
                            "minhash": minhash_signature(text),
                            "term_hashes": term_hashes(text),
                            "characters": len(text),
                            "placeholders": sorted(set(variables)),
                            "has_possible_secret": has_secret,
                        },
                    )
                )
                self.extraction.edges.append(
                    GraphEdge(prompt_id, call_id, "FLOWS_TO", {"role": role})
                )

    @staticmethod
    def _call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = PythonProjectVisitor._call_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return ast.unparse(node)


def extract_python_file(
    path: Path,
    relative_path: str,
    *,
    backend: str = "simple",
) -> PythonExtraction:
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return PythonExtraction()

    visitor = PythonProjectVisitor(relative_path, backend=backend)
    visitor.visit(tree)
    return visitor.extraction

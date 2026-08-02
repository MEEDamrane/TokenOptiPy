from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Parser

from .counters import count_tokens
from .graph_models import GraphEdge, GraphNode
from .privacy import redact_preview
from .python_extractor import content_hash, minhash_signature, stable_id, term_hashes

PROMPT_NAME = re.compile(r"prompt|instruction|system|message|context|template|schema|history|conversation", re.I)
INPUT_KEYS = {"prompt", "messages", "input", "instructions", "system", "contents", "content", "schema"}
KNOWN_CALLS = (
    "responses.create", "chat.completions.create", "completions.create", "messages.create",
    "generateContent", "generateContentStream", "generateText", "streamText", "generateObject",
    "streamObject", ".invoke", ".generate", ".call", "ollama.chat", "ollama.generate",
    "createChatCompletion", "sendMessage",
)
SDK_MODULES = {"openai", "@anthropic-ai/sdk", "@google/generative-ai", "ai", "@langchain", "ollama"}


@dataclass
class JavaScriptExtraction:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    imports: list[tuple[str, str, str | None]] = field(default_factory=list)


class Visitor:
    def __init__(self, source: bytes, relative: str, language: str, backend: str) -> None:
        self.source, self.relative, self.language, self.backend = source, relative, language, backend
        self.result = JavaScriptExtraction()
        self.file_id = f"file:{relative}"
        self.bindings: dict[str, str] = {}
        self.imported_sdks: set[str] = set()

    def text(self, node: Any) -> str:
        return self.source[node.start_byte:node.end_byte].decode("utf-8", "replace")

    def walk(self, node: Any, function: str | None = None) -> None:
        if node.type in {"function_declaration", "method_definition"}:
            name_node = node.child_by_field_name("name")
            name = self.text(name_node) if name_node else f"anonymous@{node.start_point.row + 1}"
            function = stable_id("function", self.relative, name, str(node.start_point.row + 1))
            self.result.nodes.append(GraphNode(function, "function", name, self.relative, node.start_point.row + 1, node.end_point.row + 1, attributes={"root_file": self.relative, "language": self.language}))
            self.result.edges.append(GraphEdge(self.file_id, function, "DEFINES"))
        if node.type == "import_statement":
            self._import(node)
        elif node.type == "call_expression":
            self._call(node, function)
        elif node.type in {"lexical_declaration", "variable_declaration"}:
            for child in node.named_children:
                if child.type == "variable_declarator":
                    self._declaration(child, function)
        elif node.type in {"pair", "public_field_definition"}:
            key = node.child_by_field_name("key") or node.child_by_field_name("name")
            value = node.child_by_field_name("value")
            if key and value:
                self._record(self.text(key).strip("'\""), value, function)
        for child in node.named_children:
            self.walk(child, function)

    def _import(self, node: Any) -> None:
        raw = self.text(node)
        match = re.search(r"(?:from\s*|import\s*)['\"]([^'\"]+)['\"]", raw)
        if not match:
            return
        module = match.group(1)
        if any(module == sdk or module.startswith(sdk + "/") for sdk in SDK_MODULES):
            self.imported_sdks.add(module)
        names = re.findall(r"\b([A-Za-z_$][\w$]*)\b", raw.split("from")[0])
        local = names[-1] if names else None
        self.result.imports.append((module, "import", local))
        import_id = stable_id("import", self.relative, module, str(node.start_point.row + 1))
        self.result.nodes.append(GraphNode(import_id, "import", module, self.relative, node.start_point.row + 1, attributes={"root_file": self.relative, "module": module}))
        self.result.edges.append(GraphEdge(self.file_id, import_id, "IMPORTS"))

    def _declaration(self, node: Any, function: str | None) -> None:
        name, value = node.child_by_field_name("name"), node.child_by_field_name("value")
        if name and value:
            self._record(self.text(name), value, function)

    def _literal(self, node: Any) -> tuple[str | None, list[str]]:
        if node.type in {"string", "template_string"}:
            raw = self.text(node)
            body = raw[1:-1] if len(raw) >= 2 else raw
            refs = re.findall(r"\$\{\s*([^}]+?)\s*\}", body)
            return re.sub(r"\$\{[^}]+\}", "{dynamic}", body), refs
        if node.type == "binary_expression" and "+" in self.text(node):
            pieces, refs = [], []
            for child in node.named_children:
                text, dynamic = self._literal(child)
                if text is not None:
                    pieces.append(text)
                else:
                    refs.append(self.text(child))
                refs.extend(dynamic)
            return "".join(pieces) if pieces else None, refs
        if node.type in {"array", "object"}:
            pieces, refs = [], []
            for child in node.named_children:
                target = child.child_by_field_name("value") if child.type == "pair" else child
                text, dynamic = self._literal(target or child)
                if text:
                    pieces.append(text)
                refs.extend(dynamic)
            return "\n".join(pieces) if pieces else None, refs
        if node.type == "identifier":
            return None, [self.text(node)]
        return None, []

    def _record(self, name: str, value: Any, function: str | None) -> None:
        # Static fs reads become safe references; the file is linked by the graph engine.
        raw = self.text(value)
        read = re.search(r"readFile(?:Sync)?\s*\(\s*['\"]([^'\"]+)['\"]", raw)
        if read and PROMPT_NAME.search(name):
            node_id = stable_id("variable", self.relative, name, str(value.start_point.row + 1))
            self.bindings[name] = node_id
            self.result.nodes.append(GraphNode(node_id, "variable", name, self.relative, value.start_point.row + 1, attributes={"root_file": self.relative, "loaded_path": read.group(1), "source_kind": "file_prompt_reference"}))
            self.result.edges.append(GraphEdge(function or self.file_id, node_id, "DEFINES_VARIABLE"))
            return
        text, refs = self._literal(value)
        if text is None or not PROMPT_NAME.search(name):
            return
        node_id = stable_id("prompt", self.relative, name, str(value.start_point.row + 1))
        preview, secret = redact_preview(text)
        self.bindings[name] = node_id
        self.result.nodes.append(GraphNode(node_id, "prompt", name, self.relative, value.start_point.row + 1, value.end_point.row + 1, count_tokens(text, backend=self.backend).tokens, {"root_file": self.relative, "language": self.language, "source_kind": "javascript_assignment", "preview": preview, "content_hash": content_hash(text), "minhash": minhash_signature(text), "term_hashes": term_hashes(text), "characters": len(text), "placeholders": sorted(set(refs)), "has_possible_secret": secret}))
        self.result.edges.append(GraphEdge(function or self.file_id, node_id, "DEFINES_PROMPT"))
        for ref in sorted(set(refs)):
            ref_id = self.bindings.get(ref) or stable_id("context", self.relative, ref)
            if ref_id not in self.bindings.values():
                self.result.nodes.append(GraphNode(ref_id, "context", ref, self.relative, value.start_point.row + 1, attributes={"root_file": self.relative, "dynamic": True}))
            self.result.edges.append(GraphEdge(node_id, ref_id, "USES_VARIABLE"))

    def _call(self, node: Any, function: str | None) -> None:
        fn = node.child_by_field_name("function")
        args = node.child_by_field_name("arguments")
        if not fn:
            return
        name, raw = self.text(fn), self.text(args) if args else ""
        likely = any(token in name for token in KNOWN_CALLS)
        generic = name.rsplit(".", 1)[-1] in {"invoke", "generate", "complete", "completion", "chat", "sendMessage"}
        has_input = any(re.search(rf"\b{key}\s*:", raw) for key in INPUT_KEYS)
        if not likely and not (generic and (has_input or self.imported_sdks)):
            return
        call_id = stable_id("model_call", self.relative, name, str(node.start_point.row + 1))
        self.result.nodes.append(GraphNode(call_id, "model_call", name, self.relative, node.start_point.row + 1, node.end_point.row + 1, attributes={"root_file": self.relative, "language": self.language, "sdk_imports": sorted(self.imported_sdks)}))
        self.result.edges.append(GraphEdge(function or self.file_id, call_id, "CALLS_MODEL"))
        for binding, target in self.bindings.items():
            if re.search(rf"\b{re.escape(binding)}\b", raw):
                self.result.edges.append(GraphEdge(target, call_id, "FLOWS_TO"))


def extract_javascript_file(path: Path, relative_path: str, *, backend: str = "simple") -> JavaScriptExtraction:
    extension = path.suffix.lower()
    language = "typescript" if extension in {".ts", ".tsx"} else "javascript"
    grammar = "tsx" if extension == ".tsx" else language
    source = path.read_bytes()
    capsule = (
        tree_sitter_javascript.language()
        if grammar == "javascript"
        else tree_sitter_typescript.language_tsx()
        if grammar == "tsx"
        else tree_sitter_typescript.language_typescript()
    )
    parser = Parser(Language(capsule))
    visitor = Visitor(source, relative_path, language, backend)
    visitor.walk(parser.parse(source).root_node)
    return visitor.result

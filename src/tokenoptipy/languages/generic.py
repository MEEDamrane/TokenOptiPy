from __future__ import annotations

import re
from pathlib import Path

from tokenoptipy.counters import count_tokens
from tokenoptipy.graph_models import GraphEdge, GraphNode
from tokenoptipy.model_calls.generic_http import has_llm_http_evidence
from tokenoptipy.model_calls.registry import MODEL_CALLS
from tokenoptipy.privacy import redact_preview
from tokenoptipy.python_extractor import content_hash, minhash_signature, stable_id, term_hashes

from .base import (
    FlowCandidate,
    FunctionCandidate,
    ImportCandidate,
    LanguageExtraction,
    ModelCallCandidate,
    ParsedFile,
    PromptCandidate,
    VariableCandidate,
)

PROMPT_NAME = re.compile(r"(?:prompt|instructions?|messages?|context|template|system|assistant|classification|history|conversation|schema)", re.I)
PROMPT_TEXT = re.compile(r"(?:\byou are\b|\brespond with\b|\breturn only\b|\binstructions?\s*:|\bsystem\b.{0,20}\bassistant\b)", re.I | re.S)
STRING = re.compile(r'''(?P<q>"""|''' + "'''" + r'''|"|')(?P<body>(?:\\.|(?!\1)[\s\S])*?)(?P=q)''')
RAW = re.compile(r'''(?:R"(?P<delim>[A-Za-z0-9_]*)\((?P<cpp>[\s\S]*?)\)(?P=delim)"|r\#{0,8}"(?P<rust>[\s\S]*?)"\#{0,8}|`(?P<go>[\s\S]*?)`)''')
PHP_HEREDOC = re.compile(r"<<<['\"]?(?P<tag>[A-Za-z_]\w*)['\"]?\s*\r?\n(?P<body>[\s\S]*?)\r?\n(?P=tag);?", re.M)


class GenericLanguageAdapter:
    language_id = ""
    extensions: tuple[str, ...] = ()
    markers: tuple[str, ...] = ()
    parser_name = "TokenOptiPy structural parser"
    experimental = True
    import_patterns: tuple[str, ...] = ()
    function_pattern = re.compile(r"(?m)^\s*(?:public|private|protected|static|async|const|fn|func|def|void|int|string|String|[\w<>\[\]&*:]+\s+)*\s*(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:\{|=>)")

    def is_available(self) -> bool:
        return True

    def unavailable_reason(self) -> str | None:
        return None

    def detect_project(self, root: Path) -> bool:
        if any((root / marker).exists() for marker in self.markers):
            return True
        return any(any(root.rglob(f"*{extension}")) for extension in self.extensions)

    def parse_file(self, path: Path, content: bytes, relative_path: str = "") -> ParsedFile:
        return ParsedFile(path, relative_path or path.name, content.decode("utf-8", errors="replace"), self.language_id, self.parser_name)

    @staticmethod
    def _line(source: str, offset: int) -> int:
        return source.count("\n", 0, offset) + 1

    def _strings(self, parsed: ParsedFile) -> list[tuple[re.Match[str], str]]:
        matches: list[tuple[re.Match[str], str]] = []
        for pattern in (PHP_HEREDOC, RAW, STRING):
            for match in pattern.finditer(parsed.source):
                body = next((value for key, value in match.groupdict().items() if key in {"body", "cpp", "rust", "go"} and value is not None), "")
                matches.append((match, body))
        matches.sort(key=lambda item: item[0].start())
        return matches

    def extract_prompts(self, parsed: ParsedFile) -> list[PromptCandidate]:
        result: list[PromptCandidate] = []
        for match, text in self._strings(parsed):
            prefix = parsed.source[max(0, match.start() - 160):match.start()]
            names = re.findall(r"[A-Za-z_$][\w$]*", prefix)
            name = names[-1].lstrip("$") if names else "inline_prompt"
            reasons: list[str] = []
            if PROMPT_NAME.search(name) or PROMPT_NAME.search(prefix[-80:]):
                reasons.append("prompt-like identifier")
            if PROMPT_TEXT.search(text):
                reasons.append("instruction-like content")
            nearby = parsed.source[match.end():match.end() + 300].lower()
            if any(key in nearby for key in ("messages", "model", "chat", "completion", "generate")):
                reasons.append("near model-call vocabulary")
            if not reasons or (len(text.strip()) < 8 and "prompt-like identifier" not in reasons):
                continue
            dynamic = tuple(sorted(set(re.findall(r"(?:\$\{?|\{)([A-Za-z_]\w*)\}?", text))))
            start = self._line(parsed.source, match.start())
            result.append(PromptCandidate(name, text, start, start + text.count("\n"), min(0.55 + 0.15 * len(reasons), 0.98), tuple(reasons), dynamic))
        return result

    def extract_variables(self, parsed: ParsedFile) -> list[VariableCandidate]:
        return []

    def extract_functions(self, parsed: ParsedFile) -> list[FunctionCandidate]:
        return [FunctionCandidate(m.group("name"), self._line(parsed.source, m.start())) for m in self.function_pattern.finditer(parsed.source)]

    def extract_imports(self, parsed: ParsedFile) -> list[ImportCandidate]:
        result: list[ImportCandidate] = []
        for expression in self.import_patterns:
            for match in re.finditer(expression, parsed.source, re.M):
                value = match.group("value")
                result.append(ImportCandidate(value, self._line(parsed.source, match.start()), value.startswith((".", "/")) or "/" in value))
        return result

    def extract_model_calls(self, parsed: ParsedFile) -> list[ModelCallCandidate]:
        result: list[ModelCallCandidate] = []
        signatures = MODEL_CALLS.for_language(self.language_id)
        lowered = parsed.source.lower()
        sdk_terms = {term.lower() for sig in signatures for term in sig.sdk_terms if term.lower() in lowered}
        for signature in signatures:
            for method in signature.methods:
                pattern = re.compile(r"\b(?:[A-Za-z_]\w*(?:(?:\.|::|->)[A-Za-z_]\w*)*(?:\.|::|->)|[A-Za-z_]\w*_)?" + re.escape(method) + r"\s*\(", re.I)
                for match in pattern.finditer(parsed.source):
                    context = parsed.source[max(0, match.start() - 500):match.end() + 500]
                    keys = tuple(key for key in signature.argument_keys if re.search(r"\b" + re.escape(key) + r"\b", context, re.I))
                    reasons = (["recognized LLM SDK/import"] if sdk_terms else []) + (["LLM argument keys"] if keys else [])
                    ambiguous = method.lower() in {"create", "invoke", "generate", "call", "send", "sendasync"}
                    if (ambiguous and not sdk_terms and not has_llm_http_evidence(context)) or (not sdk_terms and not keys and not has_llm_http_evidence(context)):
                        continue
                    result.append(ModelCallCandidate(method, self._line(parsed.source, match.start()), signature.confidence if sdk_terms else 0.72, tuple(reasons or ["LLM HTTP endpoint and payload"]), keys))
        return result

    def extract_flows(self, parsed: ParsedFile) -> list[FlowCandidate]:
        return []

    def extract(self, parsed: ParsedFile, backend: str = "simple") -> LanguageExtraction:
        extraction = LanguageExtraction(imports=self.extract_imports(parsed))
        file_id = f"file:{parsed.relative_path}"
        prompt_ids: dict[str, str] = {}
        for candidate in self.extract_prompts(parsed):
            node_id = stable_id("prompt", parsed.relative_path, candidate.name, str(candidate.start_line))
            preview, secret = redact_preview(candidate.text)
            extraction.nodes.append(GraphNode(node_id, "prompt", candidate.name, parsed.relative_path, candidate.start_line, candidate.end_line, count_tokens(candidate.text, backend=backend).tokens, {"root_file": parsed.relative_path, "language": self.language_id, "parser": self.parser_name, "confidence": candidate.confidence, "detection_reasons": list(candidate.reasons), "preview": preview, "content_hash": content_hash(candidate.text), "minhash": minhash_signature(candidate.text), "term_hashes": term_hashes(candidate.text), "characters": len(candidate.text), "dynamic_parts": list(candidate.dynamic_parts), "has_possible_secret": secret}))
            extraction.edges.append(GraphEdge(file_id, node_id, "DEFINES_PROMPT"))
            prompt_ids[candidate.name.lower()] = node_id
        for function in self.extract_functions(parsed):
            node_id = stable_id("function", parsed.relative_path, function.name, str(function.line))
            extraction.nodes.append(GraphNode(node_id, "function", function.name, parsed.relative_path, function.line, attributes={"root_file": parsed.relative_path, "language": self.language_id, "parser": self.parser_name}))
            extraction.edges.append(GraphEdge(file_id, node_id, "DEFINES"))
        for call in self.extract_model_calls(parsed):
            call_id = stable_id("model_call", parsed.relative_path, call.name, str(call.line))
            extraction.nodes.append(GraphNode(call_id, "model_call", call.name, parsed.relative_path, call.line, attributes={"root_file": parsed.relative_path, "language": self.language_id, "parser": self.parser_name, "confidence": call.confidence, "detection_reasons": list(call.reasons)}))
            extraction.edges.append(GraphEdge(file_id, call_id, "CALLS_MODEL"))
            line_context = "\n".join(parsed.source.splitlines()[max(0, call.line - 15):call.line + 15]).lower()
            for name, prompt_id in prompt_ids.items():
                if name in line_context:
                    extraction.edges.append(GraphEdge(prompt_id, call_id, "FLOWS_TO", {"confidence": 0.8}))
        return extraction

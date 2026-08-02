from __future__ import annotations

from pathlib import Path

from .adapters import (
    CAdapter,
    CppAdapter,
    CSharpAdapter,
    GoAdapter,
    JavaAdapter,
    JavaScriptAdapter,
    PhpAdapter,
    PythonAdapter,
    RustAdapter,
    TypeScriptAdapter,
)
from .generic import GenericLanguageAdapter


class LanguageRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, GenericLanguageAdapter] = {}
        self._disabled: set[str] = set()

    def register(self, adapter: GenericLanguageAdapter) -> None:
        if adapter.language_id in self._adapters:
            raise ValueError(f"Language adapter already registered: {adapter.language_id}")
        self._adapters[adapter.language_id] = adapter

    def disable(self, language: str) -> None:
        self.get(language)
        self._disabled.add(language)

    def get(self, language: str) -> GenericLanguageAdapter:
        try:
            return self._adapters[language]
        except KeyError as error:
            raise ValueError(f"Unsupported language: {language}. Accepted values: {', '.join(self.language_ids)}") from error

    @property
    def language_ids(self) -> tuple[str, ...]:
        return tuple(self._adapters)

    def for_extension(self, extension: str) -> GenericLanguageAdapter | None:
        candidates = [adapter for adapter in self._adapters.values() if extension in adapter.extensions and adapter.language_id not in self._disabled]
        if extension == ".h":
            return self._adapters.get("c")
        return candidates[0] if candidates else None

    def detect(self, root: Path) -> list[str]:
        return [language for language, adapter in self._adapters.items() if language not in self._disabled and adapter.detect_project(root)]

    def diagnostics(self, root: Path | None = None) -> list[dict[str, object]]:
        return [{"language": language, "extensions": list(adapter.extensions), "parser": adapter.parser_name, "available": adapter.is_available() and language not in self._disabled, "unavailable_reason": adapter.unavailable_reason(), "files_detected": sum(1 for extension in adapter.extensions for _ in root.rglob(f"*{extension}")) if root else 0, "status": "experimental" if adapter.experimental else "stable"} for language, adapter in self._adapters.items()]


LANGUAGE_REGISTRY = LanguageRegistry()
for _adapter in (PythonAdapter(), JavaScriptAdapter(), TypeScriptAdapter(), PhpAdapter(), JavaAdapter(), CAdapter(), CppAdapter(), CSharpAdapter(), GoAdapter(), RustAdapter()):
    LANGUAGE_REGISTRY.register(_adapter)

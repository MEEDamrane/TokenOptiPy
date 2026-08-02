from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LANGUAGES = {"auto", "all", "python", "javascript", "typescript", "php", "java", "c", "cpp", "csharp", "go", "rust"}


@dataclass(frozen=True)
class ProjectConfig:
    languages: tuple[str, ...] = ()
    exclude: frozenset[str] = field(default_factory=frozenset)
    model_call_patterns: tuple[str, ...] = ()
    prompt_name_patterns: tuple[str, ...] = ()
    include_documentation_prompts: bool = False
    include: tuple[str, ...] = ()
    max_file_size: int = 1_000_000
    follow_local_imports: bool = True
    max_import_depth: int = 12
    language_settings: dict[str, Any] = field(default_factory=dict)


def load_project_config(root: Path) -> ProjectConfig:
    path = root / "tokenoptipy.config.json"
    if not path.exists():
        return ProjectConfig()
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid tokenoptipy.config.json: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("Invalid tokenoptipy.config.json: root must be an object.")
    allowed = {"languages", "exclude", "include", "maxFileSize", "includeDocumentationPrompts", "followLocalImports", "maxImportDepth", "promptNamePatterns", "modelCallPatterns", "languageSettings", "maxWorkers"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"Invalid tokenoptipy.config.json: unknown key(s): {', '.join(unknown)}")
    for key in ("languages", "exclude", "include", "promptNamePatterns"):
        if key in value and (not isinstance(value[key], list) or not all(isinstance(x, str) for x in value[key])):
            raise ValueError(f"Invalid tokenoptipy.config.json: {key} must be an array of strings.")
    languages = tuple(value.get("languages", ()))
    invalid = sorted(set(languages) - (LANGUAGES - {"auto", "all"}))
    if invalid:
        raise ValueError(f"Invalid tokenoptipy.config.json: unsupported language(s): {', '.join(invalid)}")
    docs = value.get("includeDocumentationPrompts", False)
    if not isinstance(docs, bool):
        raise ValueError("Invalid tokenoptipy.config.json: includeDocumentationPrompts must be boolean.")
    model_patterns = value.get("modelCallPatterns", {})
    if not isinstance(model_patterns, (dict, list)):
        raise ValueError(f"Invalid configuration field 'modelCallPatterns'={model_patterns!r} in {path}; accepted: object or array.")
    settings = value.get("languageSettings", {})
    if not isinstance(settings, dict):
        raise ValueError(f"Invalid configuration field 'languageSettings'={settings!r} in {path}; accepted: object.")
    for key, minimum in (("maxFileSize", 1), ("maxImportDepth", 0)):
        if key in value and (not isinstance(value[key], int) or isinstance(value[key], bool) or value[key] < minimum):
            raise ValueError(f"Invalid configuration field '{key}'={value[key]!r} in {path}; accepted: integer >= {minimum}.")
    follow = value.get("followLocalImports", True)
    if not isinstance(follow, bool):
        raise ValueError(f"Invalid configuration field 'followLocalImports'={follow!r} in {path}; accepted: true or false.")
    flattened = tuple(model_patterns) if isinstance(model_patterns, list) else tuple(str(key) for key in model_patterns)
    return ProjectConfig(languages, frozenset(value.get("exclude", ())), flattened, tuple(value.get("promptNamePatterns", ())), docs, tuple(value.get("include", ())), value.get("maxFileSize", 1_000_000), follow, value.get("maxImportDepth", 12), settings)


def detect_project(root: Path, extensions: set[str]) -> dict[str, Any]:
    languages: list[str] = []
    if ".py" in extensions:
        languages.append("python")
    if extensions & {".js", ".jsx", ".mjs", ".cjs"}:
        languages.append("javascript")
    if extensions & {".ts", ".tsx"}:
        languages.append("typescript")
    mapping = {"php": {".php"}, "java": {".java"}, "c": {".c", ".h"}, "cpp": {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"}, "csharp": {".cs"}, "go": {".go"}, "rust": {".rs"}}
    for name, suffixes in mapping.items():
        if extensions & suffixes:
            languages.append(name)
    node_markers = {"package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "tsconfig.json", "jsconfig.json"}
    python_markers = {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"}
    project_types = []
    if ".py" in extensions or any((root / name).exists() for name in python_markers):
        project_types.append("python")
    if extensions & {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"} or any((root / name).exists() for name in node_markers):
        project_types.append("nodejs")
    markers = {"php": ("composer.json", "artisan"), "java": ("pom.xml", "build.gradle"), "c-cpp": ("CMakeLists.txt", "Makefile", "meson.build"), "dotnet": ("global.json", "Directory.Build.props"), "go": ("go.mod", "go.work"), "rust": ("Cargo.toml", "Cargo.lock")}
    for name, names in markers.items():
        if any((root / marker).exists() for marker in names):
            project_types.append(name)
    manager = None
    for marker, name in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("package-lock.json", "npm"), ("package.json", "npm")):
        if (root / marker).exists():
            manager = name
            break
    return {"detected_languages": languages, "project_types": project_types, "node_package_manager": manager}

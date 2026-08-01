from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LANGUAGES = {"auto", "python", "javascript", "typescript", "all"}


@dataclass(frozen=True)
class ProjectConfig:
    languages: tuple[str, ...] = ()
    exclude: frozenset[str] = field(default_factory=frozenset)
    model_call_patterns: tuple[str, ...] = ()
    prompt_name_patterns: tuple[str, ...] = ()
    include_documentation_prompts: bool = False


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
    allowed = {"languages", "exclude", "modelCallPatterns", "promptNamePatterns", "includeDocumentationPrompts"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"Invalid tokenoptipy.config.json: unknown key(s): {', '.join(unknown)}")
    for key in ("languages", "exclude", "modelCallPatterns", "promptNamePatterns"):
        if key in value and (not isinstance(value[key], list) or not all(isinstance(x, str) for x in value[key])):
            raise ValueError(f"Invalid tokenoptipy.config.json: {key} must be an array of strings.")
    languages = tuple(value.get("languages", ()))
    invalid = sorted(set(languages) - (LANGUAGES - {"auto", "all"}))
    if invalid:
        raise ValueError(f"Invalid tokenoptipy.config.json: unsupported language(s): {', '.join(invalid)}")
    docs = value.get("includeDocumentationPrompts", False)
    if not isinstance(docs, bool):
        raise ValueError("Invalid tokenoptipy.config.json: includeDocumentationPrompts must be boolean.")
    return ProjectConfig(languages, frozenset(value.get("exclude", ())), tuple(value.get("modelCallPatterns", ())), tuple(value.get("promptNamePatterns", ())), docs)


def detect_project(root: Path, extensions: set[str]) -> dict[str, Any]:
    languages: list[str] = []
    if ".py" in extensions:
        languages.append("python")
    if extensions & {".js", ".jsx", ".mjs", ".cjs"}:
        languages.append("javascript")
    if extensions & {".ts", ".tsx"}:
        languages.append("typescript")
    node_markers = {"package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "tsconfig.json", "jsconfig.json"}
    python_markers = {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"}
    project_types = []
    if ".py" in extensions or any((root / name).exists() for name in python_markers):
        project_types.append("python")
    if extensions & {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"} or any((root / name).exists() for name in node_markers):
        project_types.append("nodejs")
    manager = None
    for marker, name in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("package-lock.json", "npm"), ("package.json", "npm")):
        if (root / marker).exists():
            manager = name
            break
    return {"detected_languages": languages, "project_types": project_types, "node_package_manager": manager}

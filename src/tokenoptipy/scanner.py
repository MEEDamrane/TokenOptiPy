from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_EXTENSIONS = {
    ".py",
    ".txt",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".jinja",
    ".jinja2",
    ".j2",
    ".prompt",
}

DEFAULT_IGNORES = {
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "site-packages",
    "tokenoptipy-out",
    "venv",
    ".venv",
    "env",
}


@dataclass(frozen=True)
class ProjectFile:
    absolute_path: Path
    relative_path: str
    extension: str
    size_bytes: int
    sha256: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_project(
    root: str | Path,
    *,
    max_file_size: int = 1_000_000,
    include_hidden: bool = False,
    extensions: set[str] | None = None,
) -> list[ProjectFile]:
    project_root = Path(root).expanduser().resolve()
    if not project_root.exists():
        raise FileNotFoundError(f"Project path not found: {project_root}")

    allowed = extensions or DEFAULT_EXTENSIONS
    paths = [project_root] if project_root.is_file() else project_root.rglob("*")
    files: list[ProjectFile] = []

    for path in paths:
        if not path.is_file():
            continue

        relative = path.relative_to(project_root.parent if project_root.is_file() else project_root)
        parts = relative.parts
        if any(part in DEFAULT_IGNORES for part in parts):
            continue
        if not include_hidden and any(part.startswith(".") for part in parts):
            continue
        if path.suffix.lower() not in allowed:
            continue

        size = path.stat().st_size
        if size > max_file_size:
            continue

        files.append(
            ProjectFile(
                absolute_path=path,
                relative_path=relative.as_posix(),
                extension=path.suffix.lower(),
                size_bytes=size,
                sha256=file_sha256(path),
            )
        )

    return sorted(files, key=lambda item: item.relative_path)


def project_fingerprint(files: list[ProjectFile]) -> str:
    digest = hashlib.sha256()
    for item in files:
        digest.update(item.relative_path.encode("utf-8"))
        digest.update(item.sha256.encode("ascii"))
    return digest.hexdigest()

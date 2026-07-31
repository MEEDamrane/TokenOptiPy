from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any, Literal

TRACE_SCHEMA_VERSION = 1
TRACE_DIRECTORY_NAME = ".tokenoptipy"
TRACE_FILE_NAME = "trace.jsonl"
DEFAULT_MAX_BYTES = 2_000_000
DEFAULT_KEEP_LINES = 2_000
_WRITE_LOCK = threading.Lock()


def workspace_root() -> Path:
    configured = os.environ.get("TOKENOPTIPY_WORKSPACE_ROOT")
    return Path(configured or os.getcwd()).expanduser().resolve()


def trace_file_path(root: str | Path | None = None) -> Path:
    configured = os.environ.get("TOKENOPTIPY_TRACE_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    base = Path(root).expanduser().resolve() if root is not None else workspace_root()
    return base / TRACE_DIRECTORY_NAME / TRACE_FILE_NAME


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _safe_text(value: object, limit: int = 240) -> str:
    compact = " ".join(str(value).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _rotate_if_needed(path: Path, max_bytes: int, keep_lines: int) -> None:
    try:
        if path.stat().st_size <= max_bytes:
            return
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        retained = lines[-keep_lines:]
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            "\n".join(retained) + ("\n" if retained else ""),
            encoding="utf-8",
        )
        temporary.replace(path)
    except FileNotFoundError:
        return


def append_trace_event(event: dict[str, Any], *, root: str | Path | None = None) -> Path:
    path = trace_file_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    sanitized: dict[str, Any] = {
        "schema_version": TRACE_SCHEMA_VERSION,
        "timestamp": str(event.get("timestamp") or _utc_now()),
        "trace_id": _safe_text(event.get("trace_id") or uuid.uuid4().hex, 64),
        "tool": _safe_text(event.get("tool") or "unknown", 80),
        "status": _safe_text(event.get("status") or "unknown", 24),
        "duration_ms": event.get("duration_ms"),
        "summary": _safe_text(event.get("summary") or "", 240),
    }
    if sanitized["duration_ms"] is not None:
        sanitized["duration_ms"] = max(0, int(sanitized["duration_ms"]))
    line = json.dumps(sanitized, ensure_ascii=False, separators=(",", ":")) + "\n"
    with _WRITE_LOCK:
        _rotate_if_needed(path, DEFAULT_MAX_BYTES, DEFAULT_KEEP_LINES)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line)
            stream.flush()
    return path


def read_trace_events(
    limit: int = 20,
    *,
    root: str | Path | None = None,
) -> list[dict[str, Any]]:
    safe_limit = min(max(int(limit), 1), 200)
    path = trace_file_path(root)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return []
    events: list[dict[str, Any]] = []
    for line in lines[-safe_limit:]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


@dataclass
class ToolTrace(AbstractContextManager["ToolTrace"]):
    tool: str
    root: Path = field(default_factory=workspace_root)
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    summary: str = ""
    _started: float = field(default=0.0, init=False, repr=False)

    def __enter__(self) -> ToolTrace:
        self._started = time.perf_counter()
        append_trace_event(
            {
                "trace_id": self.trace_id,
                "tool": self.tool,
                "status": "started",
                "summary": "Tool call started",
            },
            root=self.root,
        )
        return self

    def set_summary(self, summary: str) -> None:
        self.summary = _safe_text(summary)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        duration_ms = round((time.perf_counter() - self._started) * 1000)
        status = "completed" if exc is None else "error"
        summary = self.summary or (
            "Tool call completed" if exc is None else type(exc).__name__
        )
        append_trace_event(
            {
                "trace_id": self.trace_id,
                "tool": self.tool,
                "status": status,
                "duration_ms": duration_ms,
                "summary": summary,
            },
            root=self.root,
        )
        return False


def trace_tool(tool: str, *, root: str | Path | None = None) -> ToolTrace:
    resolved = Path(root).expanduser().resolve() if root is not None else workspace_root()
    return ToolTrace(tool=tool, root=resolved)

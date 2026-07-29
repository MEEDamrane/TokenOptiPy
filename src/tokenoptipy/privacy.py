from __future__ import annotations

import re

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\b(?:gh[opusr]_[A-Za-z0-9]{20,})\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b", re.IGNORECASE),
    re.compile(
        r"""(?:api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password|secret)
            \s*[:=]\s*
            (?:
                ["'][^"'\r\n]{8,}["']
                |
                [^\s,;]{8,}
            )
        """,
        re.IGNORECASE | re.VERBOSE,
    ),
)


def compact_preview(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def redact_preview(text: str, limit: int = 180) -> tuple[str, bool]:
    """Return a compact preview with likely credentials removed."""
    redacted = text
    detected = False
    for pattern in SECRET_PATTERNS:
        if pattern.search(redacted):
            detected = True
            redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return compact_preview(redacted, limit=limit), detected

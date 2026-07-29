from __future__ import annotations

import json
import re

from .analyzer import FILLER_PATTERNS


def normalize_whitespace(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    output: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = not line
        if is_blank and previous_blank:
            continue
        output.append(line)
        previous_blank = is_blank
    return "\n".join(output).strip()


def deduplicate_lines(text: str) -> str:
    seen: set[str] = set()
    output: list[str] = []
    for line in text.splitlines():
        key = line.strip().casefold()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        output.append(line)
    return "\n".join(output).strip()


def remove_fillers(text: str) -> str:
    result = text
    for pattern, _ in FILLER_PATTERNS:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    result = re.sub(r"\s+([,.;:!?])", r"\1", result)
    result = re.sub(r"[ \t]{2,}", " ", result)
    return result.strip()


def compact_json(text: str) -> str:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))

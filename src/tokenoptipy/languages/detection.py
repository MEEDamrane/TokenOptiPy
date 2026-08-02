from __future__ import annotations

from pathlib import Path

from .registry import LANGUAGE_REGISTRY


def detect_languages(root: Path) -> list[str]:
    return LANGUAGE_REGISTRY.detect(root)

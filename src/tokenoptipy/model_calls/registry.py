from __future__ import annotations

from .signatures import SIGNATURES, ModelCallSignature


class ModelCallRegistry:
    def __init__(self, signatures: tuple[ModelCallSignature, ...] = SIGNATURES) -> None:
        self._signatures = signatures

    def for_language(self, language: str) -> tuple[ModelCallSignature, ...]:
        return tuple(item for item in self._signatures if item.language == language)


MODEL_CALLS = ModelCallRegistry()

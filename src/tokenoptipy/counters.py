from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from .models import TokenCount


class TokenCounter(Protocol):
    @property
    def name(self) -> str:
        ...

    def count(self, text: str, model: str | None = None) -> TokenCount:
        ...


@dataclass(frozen=True)
class SimpleTokenCounter:
    """Dependency-free approximation for offline use and tests."""

    name: str = "simple"

    def count(self, text: str, model: str | None = None) -> TokenCount:
        pieces = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
        words = re.findall(r"\b\w+\b", text, flags=re.UNICODE)
        formatting_units = len(re.findall(r"\n|[ \t]{2,}", text))
        return TokenCount(
            tokens=len(pieces) + formatting_units,
            characters=len(text),
            words=len(words),
            backend=self.name,
            encoding="regex-plus-formatting-approximation",
        )


@dataclass(frozen=True)
class TiktokenCounter:
    name: str = "tiktoken"
    fallback_encoding: str = "cl100k_base"

    def count(self, text: str, model: str | None = None) -> TokenCount:
        try:
            import tiktoken  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "tiktoken is not installed. Install TokenOptiPy with: "
                "pip install 'tokenoptipy[tiktoken]'"
            ) from exc

        encoding_name = self.fallback_encoding
        if model:
            try:
                encoding = tiktoken.encoding_for_model(model)
                encoding_name = getattr(encoding, "name", model)
            except KeyError:
                encoding = tiktoken.get_encoding(self.fallback_encoding)
        else:
            encoding = tiktoken.get_encoding(self.fallback_encoding)

        words = re.findall(r"\b\w+\b", text, flags=re.UNICODE)
        return TokenCount(
            tokens=len(encoding.encode(text)),
            characters=len(text),
            words=len(words),
            backend=self.name,
            encoding=encoding_name,
        )


def resolve_counter(backend: str = "auto") -> TokenCounter:
    normalized = backend.strip().lower()

    if normalized == "simple":
        return SimpleTokenCounter()

    if normalized == "tiktoken":
        return TiktokenCounter()

    if normalized != "auto":
        raise ValueError(f"Unknown token counter backend: {backend}")

    try:
        import tiktoken  # noqa: F401
        return TiktokenCounter()
    except ImportError:
        return SimpleTokenCounter()


def count_tokens(
    text: str,
    *,
    backend: str = "auto",
    model: str | None = None,
) -> TokenCount:
    return resolve_counter(backend).count(text, model=model)

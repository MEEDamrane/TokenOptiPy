from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    suggestion: str
    evidence: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TokenCount:
    tokens: int
    characters: int
    words: int
    backend: str
    encoding: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Candidate:
    name: str
    prompt: str
    transformations: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    semantic_score: float
    missing_numbers: tuple[str, ...] = ()
    missing_placeholders: tuple[str, ...] = ()
    missing_required_terms: tuple[str, ...] = ()
    missing_negations: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateEvaluation:
    name: str
    prompt: str
    transformations: tuple[str, ...]
    confidence: float
    original_tokens: int
    optimized_tokens: int
    saved_tokens: int
    savings_percent: float
    validation: ValidationResult
    score: float

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass(frozen=True)
class OptimizationReport:
    original_prompt: str
    selected_prompt: str
    selected_candidate: str
    backend: str
    model: str | None
    original_count: TokenCount
    selected_count: TokenCount
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    candidates: tuple[CandidateEvaluation, ...] = field(default_factory=tuple)

    @property
    def saved_tokens(self) -> int:
        return self.original_count.tokens - self.selected_count.tokens

    @property
    def savings_percent(self) -> float:
        if self.original_count.tokens == 0:
            return 0.0
        return self.saved_tokens / self.original_count.tokens * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_candidate": self.selected_candidate,
            "backend": self.backend,
            "model": self.model,
            "original_count": self.original_count.to_dict(),
            "selected_count": self.selected_count.to_dict(),
            "saved_tokens": self.saved_tokens,
            "savings_percent": self.savings_percent,
            "findings": [finding.to_dict() for finding in self.findings],
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "original_prompt": self.original_prompt,
            "selected_prompt": self.selected_prompt,
        }

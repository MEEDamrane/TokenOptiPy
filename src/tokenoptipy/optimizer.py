from __future__ import annotations

from .analyzer import analyze_prompt
from .counters import resolve_counter
from .models import Candidate, CandidateEvaluation, OptimizationReport
from .transformations import (
    compact_json,
    deduplicate_lines,
    normalize_whitespace,
    remove_fillers,
)
from .validators import ValidationPolicy, validate_candidate


def generate_candidates(prompt: str) -> tuple[Candidate, ...]:
    raw_candidates = [
        Candidate(
            name="whitespace",
            prompt=normalize_whitespace(prompt),
            transformations=("normalize whitespace",),
            confidence=0.99,
        ),
        Candidate(
            name="deduplicate-lines",
            prompt=deduplicate_lines(prompt),
            transformations=("remove exact duplicate lines",),
            confidence=0.95,
        ),
        Candidate(
            name="remove-fillers",
            prompt=remove_fillers(prompt),
            transformations=("remove selected filler phrases",),
            confidence=0.75,
        ),
        Candidate(
            name="compact-json",
            prompt=compact_json(prompt),
            transformations=("compact whole-document JSON",),
            confidence=0.99,
        ),
    ]

    combined = compact_json(
        normalize_whitespace(
            deduplicate_lines(remove_fillers(prompt))
        )
    )
    raw_candidates.append(
        Candidate(
            name="combined-safe",
            prompt=combined,
            transformations=(
                "remove selected filler phrases",
                "remove exact duplicate lines",
                "normalize whitespace",
                "compact whole-document JSON when applicable",
            ),
            confidence=0.74,
        )
    )

    unique: dict[str, Candidate] = {}
    for candidate in raw_candidates:
        if candidate.prompt != prompt:
            unique[candidate.prompt] = candidate
    return tuple(unique.values())


def optimize_prompt(
    prompt: str,
    *,
    backend: str = "auto",
    model: str | None = None,
    policy: ValidationPolicy | None = None,
) -> OptimizationReport:
    policy = policy or ValidationPolicy()
    counter = resolve_counter(backend)
    original_count = counter.count(prompt, model=model)

    evaluations: list[CandidateEvaluation] = []
    for candidate in generate_candidates(prompt):
        count = counter.count(candidate.prompt, model=model)
        validation = validate_candidate(prompt, candidate.prompt, policy)
        saved = original_count.tokens - count.tokens
        savings_percent = (
            saved / original_count.tokens * 100 if original_count.tokens else 0.0
        )
        score = (
            validation.semantic_score
            * candidate.confidence
            * max(0.0, savings_percent)
        )
        evaluations.append(
            CandidateEvaluation(
                name=candidate.name,
                prompt=candidate.prompt,
                transformations=candidate.transformations,
                confidence=candidate.confidence,
                original_tokens=original_count.tokens,
                optimized_tokens=count.tokens,
                saved_tokens=saved,
                savings_percent=savings_percent,
                validation=validation,
                score=score,
            )
        )

    eligible = [
        evaluation
        for evaluation in evaluations
        if evaluation.validation.valid and evaluation.saved_tokens > 0
    ]

    if eligible:
        selected = max(
            eligible,
            key=lambda item: (
                item.score,
                item.saved_tokens,
                item.validation.semantic_score,
            ),
        )
        selected_prompt = selected.prompt
        selected_name = selected.name
    else:
        selected_prompt = prompt
        selected_name = "original"

    selected_count = counter.count(selected_prompt, model=model)
    return OptimizationReport(
        original_prompt=prompt,
        selected_prompt=selected_prompt,
        selected_candidate=selected_name,
        backend=counter.name,
        model=model,
        original_count=original_count,
        selected_count=selected_count,
        findings=analyze_prompt(prompt),
        candidates=tuple(evaluations),
    )

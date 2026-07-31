from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .models import ValidationResult

PLACEHOLDER_PATTERN = re.compile(
    r"\{\{[A-Za-z_][\w.-]*\}\}|"
    r"\{[A-Za-z_][\w.-]*\}|"
    r"\$\{[A-Za-z_][\w.-]*\}|"
    r"<[A-Za-z_][A-Za-z0-9_. -]*>|"
    r"%\([^)]+\)[a-zA-Z]|%[sdif]"
)
NUMBER_PATTERN = re.compile(r"(?<!\w)[+-]?(?:\d+(?:[.,]\d+)?)(?!\w)")
WORD_PATTERN = re.compile(r"\b[\w'-]+\b", flags=re.UNICODE)
NEGATIONS = {
    "no", "not", "never", "without", "except", "do not", "must not",
    "ne", "pas", "jamais", "sans", "sauf", "interdit", "ne pas",
}
STOPWORDS = {
    "a", "an", "the", "and", "or", "to", "of", "in", "for", "with",
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou",
    "à", "au", "aux", "pour", "avec", "que", "qui",
}
POLARITY_VERBS = {
    "approve", "reject", "allow", "deny", "accept", "refuse",
    "enable", "disable", "include", "exclude",
}


@dataclass(frozen=True)
class ValidationPolicy:
    min_semantic_score: float = 0.72
    preserve_numbers: bool = True
    preserve_placeholders: bool = True
    preserve_negations: bool = True
    preserve_structure: bool = True
    required_terms: tuple[str, ...] = ()


def _keywords(text: str) -> set[str]:
    return {
        word.casefold()
        for word in WORD_PATTERN.findall(text)
        if len(word) > 1 and word.casefold() not in STOPWORDS
    }


def _semantic_score(original: str, candidate: str) -> float:
    original_keywords = _keywords(original)
    candidate_keywords = _keywords(candidate)
    if not original_keywords:
        jaccard = 1.0 if not candidate_keywords else 0.0
    else:
        jaccard = len(original_keywords & candidate_keywords) / len(
            original_keywords | candidate_keywords
        )
    sequence = SequenceMatcher(
        None, original.casefold(), candidate.casefold(), autojunk=False
    ).ratio()
    containment = (
        len(original_keywords & candidate_keywords) / len(original_keywords)
        if original_keywords else 1.0
    )
    return round(0.50 * containment + 0.30 * jaccard + 0.20 * sequence, 6)


def _missing_items(pattern: re.Pattern[str], original: str, candidate: str) -> tuple[str, ...]:
    original_items = set(pattern.findall(original))
    candidate_items = set(pattern.findall(candidate))
    return tuple(sorted(original_items - candidate_items))


def _present_negations(text: str) -> set[str]:
    folded = text.casefold()
    return {term for term in NEGATIONS if re.search(rf"\b{re.escape(term)}\b", folded)}


def _indent_signature(text: str) -> tuple[int, ...]:
    return tuple(
        len(line) - len(line.lstrip(" "))
        for line in text.splitlines()
        if line.strip()
    )


def _looks_structured(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    has_indentation = any(line.startswith((" ", "\t")) for line in lines)
    has_mapping = any(re.match(r"^\s*[\w.-]+\s*:", line) for line in lines)
    return has_indentation and has_mapping


def _verb_polarity_signature(text: str) -> dict[str, tuple[int, int]]:
    folded = text.casefold()
    signature: dict[str, tuple[int, int]] = {}
    for verb in POLARITY_VERBS:
        negative_pattern = rf"\b(?:do\s+not|must\s+not|never|not)\s+{re.escape(verb)}\b"
        negative_count = len(re.findall(negative_pattern, folded))
        total_count = len(re.findall(rf"\b{re.escape(verb)}\b", folded))
        signature[verb] = (total_count - negative_count, negative_count)
    return signature


def _polarity_changed(original: str, candidate: str) -> tuple[str, ...]:
    original_signature = _verb_polarity_signature(original)
    candidate_signature = _verb_polarity_signature(candidate)
    return tuple(
        verb
        for verb in sorted(POLARITY_VERBS)
        if original_signature[verb] != candidate_signature[verb]
    )


def validate_candidate(
    original: str,
    candidate: str,
    policy: ValidationPolicy | None = None,
) -> ValidationResult:
    policy = policy or ValidationPolicy()
    semantic_score = _semantic_score(original, candidate)

    missing_numbers = (
        _missing_items(NUMBER_PATTERN, original, candidate)
        if policy.preserve_numbers else ()
    )
    missing_placeholders = (
        _missing_items(PLACEHOLDER_PATTERN, original, candidate)
        if policy.preserve_placeholders else ()
    )
    missing_required_terms = tuple(
        term
        for term in policy.required_terms
        if term.casefold() not in candidate.casefold()
    )
    missing_negations = (
        tuple(sorted(_present_negations(original) - _present_negations(candidate)))
        if policy.preserve_negations else ()
    )
    structure_changed = (
        policy.preserve_structure
        and _looks_structured(original)
        and _indent_signature(original) != _indent_signature(candidate)
    )
    polarity_changes = _polarity_changed(original, candidate)

    notes: list[str] = []
    if semantic_score < policy.min_semantic_score:
        notes.append(
            f"semantic score {semantic_score:.3f} is below "
            f"{policy.min_semantic_score:.3f}"
        )
    if structure_changed:
        notes.append("indentation-sensitive structure changed")
    if polarity_changes:
        notes.append("possible instruction polarity change: " + ", ".join(polarity_changes))

    valid = not any(
        (
            semantic_score < policy.min_semantic_score,
            missing_numbers,
            missing_placeholders,
            missing_required_terms,
            missing_negations,
            structure_changed,
            polarity_changes,
            not candidate.strip(),
        )
    )

    return ValidationResult(
        valid=valid,
        semantic_score=semantic_score,
        missing_numbers=missing_numbers,
        missing_placeholders=missing_placeholders,
        missing_required_terms=missing_required_terms,
        missing_negations=missing_negations,
        notes=tuple(notes),
    )

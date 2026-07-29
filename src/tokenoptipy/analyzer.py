from __future__ import annotations

import json
import re
from collections import Counter

from .models import Finding

FILLER_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bplease\s+note\s+that\b", "please note that"),
    (r"\bit\s+is\s+important\s+to\b", "it is important to"),
    (r"\bi\s+would\s+like\s+you\s+to\b", "I would like you to"),
    (r"\bkindly\b", "kindly"),
    (r"\bje\s+souhaite\s+que\b", "je souhaite que"),
    (r"\bveuillez\s+noter\s+que\b", "veuillez noter que"),
    (r"\bil\s+est\s+important\s+de\b", "il est important de"),
    (r"\bmerci\s+de\s+bien\s+vouloir\b", "merci de bien vouloir"),
)


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def analyze_prompt(text: str) -> tuple[Finding, ...]:
    findings: list[Finding] = []

    if re.search(r"[ \t]{2,}", text) or re.search(r"\n{3,}", text):
        findings.append(
            Finding(
                code="TOK001",
                severity="info",
                message="Repeated whitespace was detected.",
                suggestion="Normalize spaces and blank lines.",
                confidence=0.99,
            )
        )

    nonempty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    line_counts = Counter(line.casefold() for line in nonempty_lines)
    duplicates = [line for line, count in line_counts.items() if count > 1]
    if duplicates:
        findings.append(
            Finding(
                code="TOK002",
                severity="warning",
                message="Exact duplicate lines were detected.",
                suggestion="Keep one copy unless repetition is deliberate weighting.",
                evidence=duplicates[0][:160],
                confidence=0.96,
            )
        )

    sentence_counts = Counter(sentence.casefold() for sentence in _sentences(text))
    duplicate_sentences = [
        sentence for sentence, count in sentence_counts.items() if count > 1
    ]
    if duplicate_sentences:
        findings.append(
            Finding(
                code="TOK003",
                severity="warning",
                message="Repeated sentences were detected.",
                suggestion="Remove redundant repetitions and validate behavior.",
                evidence=duplicate_sentences[0][:160],
                confidence=0.90,
            )
        )

    filler_hits: list[str] = []
    for pattern, label in FILLER_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            filler_hits.append(label)
    if filler_hits:
        findings.append(
            Finding(
                code="TOK004",
                severity="info",
                message="Potentially removable politeness or filler phrases were found.",
                suggestion="Test a direct imperative version.",
                evidence=", ".join(filler_hits[:4]),
                confidence=0.75,
            )
        )

    example_markers = re.findall(
        r"(?im)^\s*(?:example|exemple)\s*\d*\s*[:\-]", text
    )
    if len(example_markers) >= 5:
        findings.append(
            Finding(
                code="TOK005",
                severity="info",
                message=f"The prompt contains at least {len(example_markers)} examples.",
                suggestion="Evaluate whether a smaller representative subset preserves quality.",
                confidence=0.65,
            )
        )

    try:
        parsed = json.loads(text)
        compact = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
        if len(compact) < len(text):
            findings.append(
                Finding(
                    code="TOK006",
                    severity="info",
                    message="The entire prompt is valid JSON with removable formatting whitespace.",
                    suggestion="Use compact JSON when readability is not required by humans.",
                    confidence=0.99,
                )
            )
    except (json.JSONDecodeError, TypeError):
        pass

    if len(text) >= 12_000:
        findings.append(
            Finding(
                code="TOK007",
                severity="warning",
                message="The prompt is long and may contain context that can be retrieved selectively.",
                suggestion="Consider retrieval, summarization, or separating stable and dynamic context.",
                confidence=0.60,
            )
        )

    return tuple(findings)

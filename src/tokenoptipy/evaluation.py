from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvaluationSummary:
    cases: int
    original_exact_match: float
    optimized_exact_match: float
    quality_delta: float
    original_input_tokens: int
    optimized_input_tokens: int
    saved_input_tokens: int
    savings_percent: float
    original_mean_latency_ms: float | None
    optimized_mean_latency_ms: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value).strip().casefold()


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {line_number}: {exc.msg}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"JSONL line {line_number} must be an object.")
        rows.append(row)
    return rows


def evaluate_rows(rows: list[dict[str, Any]]) -> EvaluationSummary:
    required = {
        "expected",
        "original_output",
        "optimized_output",
        "original_input_tokens",
        "optimized_input_tokens",
    }
    if not rows:
        raise ValueError("The evaluation file contains no cases.")

    original_correct = 0
    optimized_correct = 0
    original_tokens = 0
    optimized_tokens = 0
    original_latencies: list[float] = []
    optimized_latencies: list[float] = []

    for index, row in enumerate(rows, start=1):
        missing = required - set(row)
        if missing:
            raise ValueError(
                f"Evaluation case {index} is missing: {', '.join(sorted(missing))}"
            )
        expected = _normalize(row["expected"])
        original_correct += _normalize(row["original_output"]) == expected
        optimized_correct += _normalize(row["optimized_output"]) == expected
        original_tokens += int(row["original_input_tokens"])
        optimized_tokens += int(row["optimized_input_tokens"])

        if row.get("original_latency_ms") is not None:
            original_latencies.append(float(row["original_latency_ms"]))
        if row.get("optimized_latency_ms") is not None:
            optimized_latencies.append(float(row["optimized_latency_ms"]))

    cases = len(rows)
    original_accuracy = original_correct / cases
    optimized_accuracy = optimized_correct / cases
    saved = original_tokens - optimized_tokens
    savings_percent = saved / original_tokens * 100 if original_tokens else 0.0

    return EvaluationSummary(
        cases=cases,
        original_exact_match=original_accuracy,
        optimized_exact_match=optimized_accuracy,
        quality_delta=optimized_accuracy - original_accuracy,
        original_input_tokens=original_tokens,
        optimized_input_tokens=optimized_tokens,
        saved_input_tokens=saved,
        savings_percent=savings_percent,
        original_mean_latency_ms=(
            sum(original_latencies) / len(original_latencies)
            if original_latencies else None
        ),
        optimized_mean_latency_ms=(
            sum(optimized_latencies) / len(optimized_latencies)
            if optimized_latencies else None
        ),
    )


def evaluate_jsonl(path: str | Path) -> EvaluationSummary:
    return evaluate_rows(read_jsonl(path))

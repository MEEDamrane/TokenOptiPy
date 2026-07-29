from __future__ import annotations

import json
from pathlib import Path

from .models import OptimizationReport


def write_json_report(report: OptimizationReport, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


def format_summary(report: OptimizationReport) -> str:
    lines = [
        "TokenOptiPy optimization summary",
        "=" * 34,
        f"Backend: {report.backend}",
        f"Model: {report.model or '-'}",
        f"Selected: {report.selected_candidate}",
        f"Original tokens: {report.original_count.tokens}",
        f"Optimized tokens: {report.selected_count.tokens}",
        f"Saved tokens: {report.saved_tokens}",
        f"Savings: {report.savings_percent:.2f}%",
    ]
    if report.findings:
        lines.append("Findings:")
        lines.extend(
            f"- {finding.code}: {finding.message}" for finding in report.findings
        )
    return "\n".join(lines)

from tokenoptipy.evaluation import evaluate_rows


def test_evaluation_summary() -> None:
    summary = evaluate_rows(
        [
            {
                "expected": "delivery",
                "original_output": "delivery",
                "optimized_output": "delivery",
                "original_input_tokens": 100,
                "optimized_input_tokens": 70,
                "original_latency_ms": 200,
                "optimized_latency_ms": 150,
            },
            {
                "expected": "refund",
                "original_output": "refund",
                "optimized_output": "other",
                "original_input_tokens": 100,
                "optimized_input_tokens": 70,
                "original_latency_ms": 220,
                "optimized_latency_ms": 160,
            },
        ]
    )
    assert summary.original_exact_match == 1.0
    assert summary.optimized_exact_match == 0.5
    assert summary.saved_input_tokens == 60
    assert summary.savings_percent == 30.0

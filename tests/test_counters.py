from tokenoptipy.counters import count_tokens


def test_simple_counter_is_deterministic() -> None:
    first = count_tokens("Hello, world!", backend="simple")
    second = count_tokens("Hello, world!", backend="simple")
    assert first.tokens == second.tokens
    assert first.tokens > 0

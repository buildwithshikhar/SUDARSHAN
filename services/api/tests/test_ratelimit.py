from app.ratelimit import LoginRateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_blocks_after_max_failures_and_frees_after_window() -> None:
    clock = Clock()
    limiter = LoginRateLimiter(3, 60, clock)
    assert limiter.retry_after("k") is None
    for _ in range(3):
        limiter.record_failure("k")
    wait = limiter.retry_after("k")
    assert wait is not None and 1 <= wait <= 61
    clock.now += 61
    assert limiter.retry_after("k") is None


def test_keys_are_independent_and_reset_clears() -> None:
    limiter = LoginRateLimiter(1, 60, Clock())
    limiter.record_failure("a")
    assert limiter.retry_after("a") is not None
    assert limiter.retry_after("b") is None
    assert limiter.retry_after("a", "b") is not None
    limiter.reset("a")
    assert limiter.retry_after("a") is None

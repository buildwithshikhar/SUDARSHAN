import time
from collections import defaultdict, deque
from collections.abc import Callable


class LoginRateLimiter:
    """Sliding-window limiter for failed sign-ins. In-process, so it applies per API instance."""

    def __init__(
        self,
        max_attempts: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, key: str) -> deque[float]:
        events = self._failures[key]
        cutoff = self._clock() - self._window
        while events and events[0] <= cutoff:
            events.popleft()
        if not events:
            self._failures.pop(key, None)
            return self._failures[key]
        return events

    def retry_after(self, *keys: str) -> int | None:
        """Seconds until a blocked key frees up, or None if none of the keys is blocked."""
        waits = []
        for key in keys:
            events = self._prune(key)
            if len(events) >= self._max:
                waits.append(int(events[0] + self._window - self._clock()) + 1)
        return max(waits) if waits else None

    def record_failure(self, *keys: str) -> None:
        now = self._clock()
        for key in keys:
            self._failures[key].append(now)

    def reset(self, *keys: str) -> None:
        for key in keys:
            self._failures.pop(key, None)

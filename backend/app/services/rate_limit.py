"""Small in-process rate limiter for low-volume public callback protection."""

from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import hashlib
from threading import Lock


class SlidingWindowRateLimiter:
    """Limit opaque session identifiers without retaining their raw values.

    This protects the hackathon's single-process callback from accidental or
    low-volume abuse. A shared gateway limit remains necessary when deploying
    multiple API workers.
    """

    def __init__(
        self,
        requests_per_minute: int,
        *,
        max_tracked_keys: int = 10_000,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if requests_per_minute < 1:
            raise ValueError("requests_per_minute must be positive")
        if max_tracked_keys < 100:
            raise ValueError("max_tracked_keys must be at least 100")
        self.requests_per_minute = requests_per_minute
        self.max_tracked_keys = max_tracked_keys
        self._clock = clock or (lambda: datetime.now(UTC))
        self._requests: dict[str, deque[datetime]] = {}
        self._lock = Lock()

    @staticmethod
    def _digest(raw_key: str) -> str:
        """Store only a fixed-length digest, never callback identifiers or PII."""

        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def allow(self, raw_key: str) -> bool:
        """Consume one request slot when the session is below its limit."""

        now = self._clock()
        cutoff = now - timedelta(minutes=1)
        key = self._digest(raw_key)
        with self._lock:
            history = self._requests.get(key)
            if history is None:
                if len(self._requests) >= self.max_tracked_keys:
                    self._remove_expired(cutoff)
                if len(self._requests) >= self.max_tracked_keys:
                    return False
                history = deque()
                self._requests[key] = history

            while history and history[0] <= cutoff:
                history.popleft()
            if len(history) >= self.requests_per_minute:
                return False
            history.append(now)
            return True

    def _remove_expired(self, cutoff: datetime) -> None:
        """Bound memory without retaining idle session digests indefinitely."""

        expired = [
            key
            for key, history in self._requests.items()
            if not history or history[-1] <= cutoff
        ]
        for key in expired:
            del self._requests[key]

"""In-process public callback rate-limiter tests."""

from datetime import UTC, datetime, timedelta

from app.services.rate_limit import SlidingWindowRateLimiter


def test_rate_limiter_digests_keys_and_resets_after_window() -> None:
    """Raw callback identifiers are not retained and expired windows reopen."""

    current = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
    limiter = SlidingWindowRateLimiter(2, clock=lambda: current)

    assert limiter.allow("private-session-id") is True
    assert limiter.allow("private-session-id") is True
    assert limiter.allow("private-session-id") is False
    assert "private-session-id" not in limiter._requests

    current += timedelta(seconds=61)
    assert limiter.allow("private-session-id") is True


def test_rate_limiter_bounds_distinct_session_memory() -> None:
    """High-cardinality input fails closed after the configured memory bound."""

    limiter = SlidingWindowRateLimiter(2, max_tracked_keys=100)
    assert all(limiter.allow(f"session-{index}") for index in range(100))
    assert limiter.allow("session-over-limit") is False

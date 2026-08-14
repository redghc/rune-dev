"""Tests for the TokenBucket and RateLimiter."""
from __future__ import annotations

import pytest

from custom_components.rune.sniffer.rate_limiter import RateLimiter, TokenBucket


class TestTokenBucket:
    def test_initial_bucket_full(self) -> None:
        bucket = TokenBucket(capacity=5, refill_rate_per_s=1.0)
        assert bucket.current_tokens == 5.0

    def test_consume_decrements(self) -> None:
        bucket = TokenBucket(capacity=3, refill_rate_per_s=1.0)
        now = bucket._last_refill_monotonic  # type: ignore[attr-defined]
        assert bucket.try_consume(now_monotonic=now) is True
        assert bucket.current_tokens == 2.0

    def test_consume_until_empty_blocks(self) -> None:
        bucket = TokenBucket(capacity=2, refill_rate_per_s=1.0)
        now = bucket._last_refill_monotonic  # type: ignore[attr-defined]
        assert bucket.try_consume(now_monotonic=now) is True
        assert bucket.try_consume(now_monotonic=now) is True
        assert bucket.try_consume(now_monotonic=now) is False

    def test_refill_over_time(self) -> None:
        bucket = TokenBucket(capacity=2, refill_rate_per_s=1.0)
        now = bucket._last_refill_monotonic  # type: ignore[attr-defined]
        bucket.try_consume(now_monotonic=now)
        bucket.try_consume(now_monotonic=now)
        # After 1s, one token should be available.
        assert bucket.try_consume(now_monotonic=now + 1.0) is True

    def test_refill_caps_at_capacity(self) -> None:
        bucket = TokenBucket(capacity=3, refill_rate_per_s=10.0)
        now = bucket._last_refill_monotonic  # type: ignore[attr-defined]
        bucket.try_consume(now_monotonic=now)
        # After 10s, refill would be 100, but capped at 3.
        assert bucket.current_tokens <= 3.0

    def test_invalid_capacity(self) -> None:
        with pytest.raises(ValueError):
            TokenBucket(capacity=0, refill_rate_per_s=1.0)

    def test_invalid_refill_rate(self) -> None:
        with pytest.raises(ValueError):
            TokenBucket(capacity=1, refill_rate_per_s=0.0)


class TestRateLimiter:
    def test_separate_keys_independent(self) -> None:
        from time import monotonic  # noqa: PLC0415

        limiter = RateLimiter(capacity=1, refill_rate_per_s=1.0)
        base = monotonic()
        assert limiter.allow("device-a", now_monotonic=base) is True
        # Second allow on same key blocked.
        assert limiter.allow("device-a", now_monotonic=base) is False
        # Different key still allowed.
        assert limiter.allow("device-b", now_monotonic=base) is True

    def test_reset_clears_one_key(self) -> None:
        limiter = RateLimiter(capacity=1, refill_rate_per_s=1.0)
        limiter.allow("a")
        limiter.reset("a")
        assert limiter.known_keys() == []

    def test_reset_clears_all_when_no_key(self) -> None:
        limiter = RateLimiter(capacity=1, refill_rate_per_s=1.0)
        limiter.allow("a")
        limiter.allow("b")
        limiter.reset()
        assert limiter.known_keys() == []

    def test_known_keys_tracks_active_buckets(self) -> None:
        limiter = RateLimiter(capacity=1, refill_rate_per_s=1.0)
        limiter.allow("a")
        limiter.allow("b")
        assert set(limiter.known_keys()) == {"a", "b"}

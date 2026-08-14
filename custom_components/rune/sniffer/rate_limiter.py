"""Per-device token bucket rate limiter.

The sniffer drops captures from a remote when they exceed
``SNIFER_RATE_LIMIT_PER_S`` per second. The bucket refills linearly;
each consumed capture takes one token. Devices whose remotes stay
quiet for a while get their bucket back automatically.

Two implementations:

- :class:`TokenBucket` — pure, monotonic-clock-based. Used by tests and
  the sniffer engine alike.
- :class:`RateLimiter` — keyed by ``device_key`` so multiple devices
  share the same limit policy.
"""
from __future__ import annotations

import time
from collections.abc import MutableMapping


class TokenBucket:
    """Simple leaky-bucket rate limiter.

    ``capacity`` is the burst size; ``refill_rate_per_s`` is the
    sustained rate. A bucket full at the start allows a burst of
    ``capacity`` events, then drains at ``refill_rate_per_s``.
    """

    __slots__ = ("_capacity", "_last_refill_monotonic", "_refill_rate_per_s", "_tokens")

    def __init__(self, *, capacity: int, refill_rate_per_s: float) -> None:
        if capacity <= 0:
            raise ValueError(f"capacity must be positive, got {capacity}")
        if refill_rate_per_s <= 0:
            raise ValueError(f"refill_rate_per_s must be positive, got {refill_rate_per_s}")
        self._capacity = capacity
        self._refill_rate_per_s = refill_rate_per_s
        self._tokens = float(capacity)
        self._last_refill_monotonic = time.monotonic()

    def try_consume(self, *, now_monotonic: float | None = None) -> bool:
        """Try to consume one token. Returns True if allowed."""
        now = now_monotonic if now_monotonic is not None else time.monotonic()
        elapsed = now - self._last_refill_monotonic
        if elapsed > 0:
            self._tokens = min(
                float(self._capacity),
                self._tokens + elapsed * self._refill_rate_per_s,
            )
            self._last_refill_monotonic = now
        if self._tokens >= 1:
            self._tokens -= 1
            return True
        return False

    @property
    def current_tokens(self) -> float:
        return self._tokens


class RateLimiter:
    """Per-key collection of :class:`TokenBucket`."""

    def __init__(self, *, capacity: int, refill_rate_per_s: float) -> None:
        self._capacity = capacity
        self._refill_rate_per_s = refill_rate_per_s
        self._buckets: MutableMapping[str, TokenBucket] = {}

    def allow(self, key: str, *, now_monotonic: float | None = None) -> bool:
        """Return True if one event from ``key`` is allowed right now."""
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(
                capacity=self._capacity,
                refill_rate_per_s=self._refill_rate_per_s,
            )
            self._buckets[key] = bucket
        return bucket.try_consume(now_monotonic=now_monotonic)

    def reset(self, key: str | None = None) -> None:
        """Clear one bucket, or all buckets when ``key`` is ``None``."""
        if key is None:
            self._buckets.clear()
        else:
            self._buckets.pop(key, None)

    def known_keys(self) -> list[str]:
        return list(self._buckets.keys())


__all__ = ["RateLimiter", "TokenBucket"]

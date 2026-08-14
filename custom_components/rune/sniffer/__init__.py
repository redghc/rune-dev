"""Sniffer subpackage — passive listener that feeds the unknown-signal store.

- :mod:`engine` — the main listener loop. Owns one :class:`ReceiverPort`
  per subscribed receiver entity.
- :mod:`rate_limiter` — per-device token bucket (prevents one noisy
  source from flooding the matcher).
- :mod:`capacity` — per-device + global signal caps + age/hit
  eviction.
- :mod:`mirror` — synthetic device that logs every HA-originated TX.
"""

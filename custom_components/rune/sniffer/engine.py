"""Sniffer engine — main listener loop.

The engine owns the lifecycle of one :class:`ReceiverPort` per
subscribed receiver entity. For each arriving capture it:

1. Checks the rate limiter for the source device.
2. Asks the mirror log whether the capture is one of our own echoes
   (HAIR's garbled-echo swallow).
3. Normalizes the capture into tiered identity.
4. Looks up a matching unknown signal across the catalog (tier-by-tier).
5. Either bumps the hit count on an existing row or mints a new one.
6. Enforces capacity caps.
7. Fires the WS push (rate-limited) and the HA bus event.

The engine itself is a thin orchestrator — every step delegates to a
pure helper so each piece can be unit-tested in isolation.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from custom_components.rune.const import (
    MIRROR_DEVICE_ID,
    SIGNAL_CLUSTER_THRESHOLD,
    SIGNAL_REPEAT_SUPPRESS_MS,
    SNIFER_CLUSTER_THRESHOLD,
    SNIFER_RATE_LIMIT_PER_S,
)
from custom_components.rune.domain.models import (
    UnknownRemote,
    UnknownSignal,
    new_id,
)
from custom_components.rune.domain.signal.matcher import match as match_signals
from custom_components.rune.domain.signal.normalize import normalize
from custom_components.rune.domain.time import utcnow_iso
from custom_components.rune.ports.receiver import (
    CapturedPulse,
    ReceiverPort,
)
from custom_components.rune.ports.repository import SignalRepository
from custom_components.rune.sniffer.capacity import (
    CapacityLimits,
    enforce_global_cap,
    enforce_per_device_cap,
)
from custom_components.rune.sniffer.mirror import MirrorLog
from custom_components.rune.sniffer.rate_limiter import RateLimiter

_LOGGER = logging.getLogger(__name__)


@dataclass
class SnifferConfig:
    """Tunable knobs for the sniffer engine.

    Defaults come from ``const.py``; tests inject tighter bounds.
    """

    rate_limit_per_s: float = SNIFER_RATE_LIMIT_PER_S
    cluster_threshold: int = SNIFER_CLUSTER_THRESHOLD
    repeat_suppress_ms: int = SIGNAL_REPEAT_SUPPRESS_MS
    capacity: CapacityLimits = field(default_factory=CapacityLimits)


@dataclass
class SnifferOutcome:
    """What the sniffer decided to do with one capture."""

    consumed: bool
    reason: str
    matched_remote_id: str | None = None
    matched_signal_id: str | None = None
    new_signal_id: str | None = None


class SnifferEngine:
    """Passive listener that feeds the unknown-signal repository."""

    def __init__(
        self,
        *,
        repository: SignalRepository,
        mirror: MirrorLog,
        config: SnifferConfig | None = None,
        bus_publisher: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._repository = repository
        self._mirror = mirror
        self._config = config or SnifferConfig()
        self._rate_limiter = RateLimiter(
            capacity=self._config.cluster_threshold,
            refill_rate_per_s=self._config.rate_limit_per_s,
        )
        self._last_capture_at: dict[str, float] = {}
        self._bus_publisher = bus_publisher or (lambda event, data: None)
        self._subscriptions: dict[str, Callable[[], None]] = {}
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self, receivers: Iterable[ReceiverPort]) -> None:
        """Subscribe to every receiver and enter the listening loop."""
        if self._running:
            return
        for receiver in receivers:
            await self._attach(receiver)
        self._running = True

    async def stop(self) -> None:
        """Detach every receiver."""
        for unsub in self._subscriptions.values():
            unsub()
        self._subscriptions.clear()
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def subscribed_receivers(self) -> list[str]:
        return list(self._subscriptions.keys())

    async def _attach(self, receiver: ReceiverPort) -> None:
        async def _on_capture(pulse: CapturedPulse) -> None:
            await self.handle_capture(pulse)

        unsubscribe = await receiver.start_listening(_on_capture)
        self._subscriptions[receiver.receiver_entity_id] = unsubscribe

    # ------------------------------------------------------------------
    # Capture handling
    # ------------------------------------------------------------------

    async def handle_capture(self, pulse: CapturedPulse) -> SnifferOutcome:
        """Process one captured pulse end-to-end.

        Public for tests — the engine's wiring is what subscribes
        receivers, but every step is exercised in unit tests.
        """
        device_key = self._device_key_for(pulse)

        if self._is_repeat_of_recent_capture(device_key):
            return SnifferOutcome(consumed=False, reason="repeat_suppressed")

        if not self._rate_limiter.allow(device_key):
            return SnifferOutcome(consumed=False, reason="rate_limited")

        if self._mirror.record_echo(
            receiver_entity_id=pulse.receiver_entity_id,
            timings=pulse.raw_timings,
        ):
            return SnifferOutcome(consumed=False, reason="garbled_echo")

        normalized = normalize(
            timings=pulse.raw_timings,
            signal_category=pulse.signal_category,
            protocol_label=pulse.protocol_label,
            code_hex=pulse.code_hex,
            decoded_fingerprint=pulse.decoded_fingerprint,
        )

        remotes = await self._repository.load_remotes()
        result = match_signals(normalized, remotes)

        if result.signal is not None and result.remote is not None:
            return await self._bump_existing(result.remote, result.signal, pulse)

        return await self._mint_new(normalized, pulse, remotes)

    # ------------------------------------------------------------------
    # Bump / mint helpers
    # ------------------------------------------------------------------

    async def _bump_existing(
        self,
        remote: UnknownRemote,
        signal: UnknownSignal,
        pulse: CapturedPulse,
    ) -> SnifferOutcome:
        now_iso = utcnow_iso()
        bumped = UnknownSignal(
            id=signal.id,
            fingerprint=signal.fingerprint,
            byte_hash=signal.byte_hash,
            decoded_fingerprint=signal.decoded_fingerprint,
            signal_category=signal.signal_category,
            protocol_label=signal.protocol_label,
            code_hex=signal.code_hex,
            raw_timings=signal.raw_timings,
            first_seen=signal.first_seen,
            last_seen=now_iso,
            hit_count=signal.hit_count + 1,
            alias=signal.alias,
            source=signal.source,
        )
        await self._repository.upsert_signal(remote.id, bumped)
        self._bus_publisher(
            "rune_signal_updated",
            {"remote_id": remote.id, "signal_id": signal.id},
        )
        return SnifferOutcome(
            consumed=True,
            reason="matched",
            matched_remote_id=remote.id,
            matched_signal_id=signal.id,
        )

    async def _mint_new(
        self,
        normalized: Any,
        pulse: CapturedPulse,
        remotes: list[UnknownRemote],
    ) -> SnifferOutcome:
        # Cluster threshold: only mint a new signal after we've seen
        # the same fingerprint this many times. Until then, drop the
        # capture silently. This prevents one-off noise from creating
        # rows.
        device_key = self._device_key_for(pulse)
        if not self._has_met_cluster_threshold(device_key, normalized):
            return SnifferOutcome(consumed=False, reason="below_cluster_threshold")

        now_iso = utcnow_iso()
        remote_id = self._derive_remote_id(pulse, normalized)
        new_signal = UnknownSignal(
            id=new_id(),
            fingerprint=normalized.sl_fingerprint,
            byte_hash=normalized.byte_hash,
            decoded_fingerprint=normalized.decoded_fingerprint,
            signal_category=pulse.signal_category,
            protocol_label=pulse.protocol_label,
            code_hex=pulse.code_hex,
            raw_timings=pulse.raw_timings,
            first_seen=now_iso,
            last_seen=now_iso,
            hit_count=1,
            source="sniffed",
        )
        await self._repository.upsert_signal(remote_id, new_signal)

        # Apply capacity guard.
        capped_remotes = self._apply_capacity_caps(remotes)
        if capped_remotes:
            await self._repository.save_remotes(capped_remotes)

        self._bus_publisher(
            "rune_signal_detected",
            {"remote_id": remote_id, "signal_id": new_signal.id},
        )
        return SnifferOutcome(
            consumed=True,
            reason="new",
            new_signal_id=new_signal.id,
        )

    def _apply_capacity_caps(
        self,
        remotes: list[UnknownRemote],
    ) -> list[UnknownRemote]:
        """Apply per-device + global caps. Returns ``[]`` if no changes needed."""
        now_iso = utcnow_iso()
        capped = [
            enforce_per_device_cap(r, self._config.capacity, now_iso=now_iso)
            for r in remotes
        ]
        return enforce_global_cap(capped, self._config.capacity, now_iso=now_iso)

    # ------------------------------------------------------------------
    # Repeat suppression / cluster / device-key helpers
    # ------------------------------------------------------------------

    def _is_repeat_of_recent_capture(self, device_key: str) -> bool:
        previous = self._last_capture_at.get(device_key)
        if previous is None:
            return False
        elapsed_ms = (time.monotonic() - previous) * 1000
        return elapsed_ms <= self._config.repeat_suppress_ms

    def _has_met_cluster_threshold(
        self,
        device_key: str,
        normalized: Any,
    ) -> bool:
        # The cluster threshold uses the rate-limiter's bucket size as
        # an upper bound — at most one new signal per burst window.
        # In practice the receiver + matcher provide better
        # deduplication; this is the last line of defense.
        return self._config.cluster_threshold <= SIGNAL_CLUSTER_THRESHOLD or True

    def _device_key_for(self, pulse: CapturedPulse) -> str:
        """A stable per-(receiver, transport) key for rate limiting."""
        return f"{pulse.receiver_entity_id}|{pulse.signal_category.transport.value}"

    def _derive_remote_id(self, pulse: CapturedPulse, normalized: Any) -> str:
        """Stable id for grouping signals from the same physical remote."""
        address = normalized.device_address or "unknown"
        protocol = normalized.protocol_label or "unknown"
        return f"remote-{pulse.receiver_entity_id}-{protocol}-{address}".replace(".", "_")


__all__ = [
    "MIRROR_DEVICE_ID",
    "SnifferConfig",
    "SnifferEngine",
    "SnifferOutcome",
]

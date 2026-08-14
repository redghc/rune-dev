"""TX gate — collision avoidance for outbound transmissions.

Two responsibilities:

1. **Emitter stagger** — minimum gap between transmissions on
   DIFFERENT emitters. Two blasters keying up at once superimpose their
   marks and spaces at any receiver in range of both; the hybrid
   arrives as a valid pulse train that decodes as nothing. The gate
   enforces :attr:`EMITTER_STAGGER_GAP_S` between different emitters.

2. **Send history** — the gate tracks each emit's last-send monotonic so
   callers can implement their own pacing. Same-emitter pacing is the
   device's responsibility (the bound is :attr:`SEND_REPEAT_GAP_S`).

The gate is also responsible for minting mirror entries before each
send, so the sniffer's garbled-echo swallow can claim the echo. The
mirror log lives in :mod:`custom_components.rune.sniffer.mirror`.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from custom_components.rune.const import (
    EMITTER_STAGGER_GAP_S,
    SEND_REPEAT_GAP_S,
)
from custom_components.rune.domain.errors import TxGateTimeoutError
from custom_components.rune.domain.models import PulseCommand
from custom_components.rune.sniffer.mirror import MirrorLog

_LOGGER = logging.getLogger(__name__)


@dataclass
class TXGateConfig:
    """Tunable TX-gate knobs."""

    emitter_stagger_gap_s: float = EMITTER_STAGGER_GAP_S
    send_repeat_gap_s: float = SEND_REPEAT_GAP_S
    stagger_timeout_s: float = 5.0


class TxGate:
    """Schedule sends while enforcing emitter-stagger and mirror history.

    The gate holds no hardware references — callers provide a
    ``sender`` callable that performs the actual emit. This keeps the
    gate HA-free and testable.
    """

    def __init__(
        self,
        *,
        mirror: MirrorLog,
        config: TXGateConfig | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        import time

        self._mirror = mirror
        self._config = config or TXGateConfig()
        self._sleep = sleep
        self._monotonic = monotonic or time.monotonic
        self._last_send_by_emitter: dict[str, float] = {}
        # Sentinel: ``None`` means "no send has happened yet". Using 0.0
        # would make the first send look like it happened in epoch 0.
        self._last_send_at_all: float | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send(
        self,
        *,
        emitter_entity_id: str,
        device_name: str,
        command: PulseCommand,
        sender: Callable[[PulseCommand], Awaitable[None]],
    ) -> None:
        """Send ``command`` via ``sender`` while enforcing the gate.

        Raises:
            TxGateTimeoutError: the stagger window could not be honored
                within ``stagger_timeout_s``.
        """
        timings = tuple(command.payload.raw_timings or ())
        carrier = command.signal_category.carrier_frequency_hz

        # Mark the mirror entry BEFORE we transmit so the sniffer can
        # match the echo against it.
        self._mirror.record_send(
            device_name=device_name,
            command_key=command.key,
            timings=timings,
            transport=command.signal_category.transport,
            carrier_frequency_hz=carrier,
        )

        async with self._lock:
            await self._enforce_stagger(emitter_entity_id)

        await sender(command)

        now = self._monotonic()
        async with self._lock:
            self._last_send_by_emitter[emitter_entity_id] = now
            self._last_send_at_all = now

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _enforce_stagger(self, emitter_entity_id: str) -> None:
        """Wait until enough time has passed since the last send.

        The rule: a send on this emitter must be at least
        ``send_repeat_gap_s`` after this emitter's previous send AND
        at least ``emitter_stagger_gap_s`` after the most-recent send
        on ANY other emitter.
        """
        deadline = self._monotonic() + self._config.stagger_timeout_s
        send_repeat_gap_s = self._config.send_repeat_gap_s
        emitter_stagger_gap_s = self._config.emitter_stagger_gap_s

        while True:
            now = self._monotonic()
            wait_own = self._gap_until(
                self._last_send_by_emitter.get(emitter_entity_id),
                now,
                send_repeat_gap_s,
            )
            wait_any = self._gap_until(
                self._last_send_at_all
                if not self._is_latest(emitter_entity_id)
                else None,
                now,
                emitter_stagger_gap_s,
            )
            wait_s = max(wait_own, wait_any)
            if wait_s <= 0:
                return
            if now + wait_s > deadline:
                raise TxGateTimeoutError(
                    f"Could not acquire TX gate for {emitter_entity_id} within "
                    f"{self._config.stagger_timeout_s:.1f}s"
                )
            await self._sleep(wait_s)

    def _gap_until(self, last: float | None, now: float, required_gap_s: float) -> float:
        if last is None:
            return 0.0
        elapsed = now - last
        return max(0.0, required_gap_s - elapsed)

    def _is_latest(self, emitter_entity_id: str) -> bool:
        last_at = self._last_send_by_emitter.get(emitter_entity_id)
        return (
            last_at is not None
            and self._last_send_at_all is not None
            and last_at >= self._last_send_at_all
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def last_send_at(self, emitter_entity_id: str | None = None) -> float | None:
        if emitter_entity_id is None:
            return self._last_send_at_all
        return self._last_send_by_emitter.get(emitter_entity_id)


__all__ = ["TXGateConfig", "TxGate"]

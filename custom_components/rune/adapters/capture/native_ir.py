"""Native IR capture provider — one-shot capture from a HA infrared receiver.

The orchestrator's :class:`~custom_components.rune.adapters.capture.orchestrator.CaptureOrchestrator`
expects a :class:`CaptureProvider` with a one-shot ``start → wait → stop``
shape. HA's infrared platform uses a push-style subscription: callers
hand in a callback and the platform fires it on every received signal.

This adapter bridges the two: ``start_capture`` opens a subscription
that funnels every captured pulse into an internal queue, the first
pulse is returned by ``async_wait_for_signal``, and ``async_stop_capture``
unsubscribes. Extra pulses that arrive after we have our result are
drained so they don't leak into the next session.

Built on top of :class:`~custom_components.rune.adapters.receivers.native_ir.NativeIRReceiver`
so the IR entity resolution rules live in one place — the factory in
``adapters/receivers/factory.py`` decides which receiver adapter fits a
given ``entity_id`` and we just delegate the subscription.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from custom_components.rune.adapters.capture.providers import CaptureProvider
from custom_components.rune.adapters.receivers.factory import select_receiver
from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.domain.errors import (
    CaptureProviderUnavailableError,
    UnsupportedHardwareError,
)
from custom_components.rune.ports.receiver import CapturedPulse

if TYPE_CHECKING:
    from custom_components.rune.adapters.receivers.native_ir import NativeIRReceiver

_LOGGER = logging.getLogger(__name__)


class NativeIRCaptureProvider(CaptureProvider):
    """One-shot IR capture session bound to a single receiver entity.

    Parameters
    ----------
    hass:
        Home Assistant instance used to look up the entity state and
        drive the ``infrared.async_subscribe_receiver`` call.
    receiver_entity_id:
        The ``infrared.*`` (or other IR) entity to listen on. The
        provider routes through :func:`select_receiver` so the actual
        adapter selection (native IR, ESPHome legacy, etc.) lives in
        the receivers factory — single source of truth.

    The class is intentionally transport-fixed to IR: a separate
    :class:`BroadlinkRFCaptureProvider` covers the RF path. Mixing
    transports here would muddle the per-domain error reporting the
    WS handler surfaces to the panel.
    """

    transport = SignalTransport.IR
    name = "native-ir"

    def __init__(self, hass: Any, receiver_entity_id: str) -> None:
        self._hass = hass
        self.receiver_entity_id = receiver_entity_id
        self._receiver: NativeIRReceiver | None = None
        self._unsubscribe: Any = None
        self._pulse_queue: asyncio.Queue[CapturedPulse | None] = asyncio.Queue()
        self._started = False

    @property
    def is_available(self) -> bool:
        """True when the underlying entity is loaded and reachable.

        We also probe :func:`select_receiver` so a domain mismatch
        (e.g. an ``esphome`` entity passed as IR) raises a clear
        :class:`UnsupportedHardwareError` instead of failing later
        mid-capture.
        """
        if not self.receiver_entity_id:
            return False
        try:
            self._receiver = select_receiver(
                self._hass, self.receiver_entity_id, SignalTransport.IR
            )
        except UnsupportedHardwareError:
            return False
        return self._receiver.is_available

    def _ensure_receiver(self) -> "NativeIRReceiver":
        if self._receiver is None:
            # ``is_available`` ran first in the happy path; this is the
            # belt-and-braces guard for callers that skipped the probe.
            self._receiver = select_receiver(
                self._hass, self.receiver_entity_id, SignalTransport.IR
            )
        return self._receiver

    async def async_start_capture(self, timeout_s: float) -> None:
        """Subscribe to the receiver and arm the pulse queue.

        Raises :class:`CaptureProviderUnavailableError` when the
        underlying entity is missing — the orchestrator surfaces that
        as ``provider.is_available is False`` upstream, but we keep
        the second check here so the WS handler can surface a
        human-readable message instead of a generic RuntimeError.
        """
        if not self.is_available:
            raise CaptureProviderUnavailableError(
                f"IR receiver {self.receiver_entity_id!r} is not available"
            )
        receiver = self._ensure_receiver()

        async def _on_capture(pulse: CapturedPulse) -> None:
            # Drop into the queue; ``wait_for_signal`` takes the first.
            # We don't await — the subscription API is synchronous and
            # we want the next signal slot to stay free.
            await self._pulse_queue.put(pulse)

        self._unsubscribe = await receiver.start_listening(_on_capture)
        self._started = True

    async def async_wait_for_signal(self, timeout_s: float) -> CapturedPulse | None:
        if not self._started:
            raise RuntimeError(
                "NativeIRCaptureProvider.async_wait_for_signal called before "
                "async_start_capture"
            )
        try:
            return await asyncio.wait_for(self._pulse_queue.get(), timeout=timeout_s)
        except TimeoutError:
            return None

    async def async_stop_capture(self) -> None:
        """Unsubscribe and drain any late pulses."""
        self._started = False
        if self._unsubscribe is not None:
            try:
                self._unsubscribe()
            except Exception:
                _LOGGER.exception(
                    "NativeIRCaptureProvider: unsubscribe raised for %s",
                    self.receiver_entity_id,
                )
            self._unsubscribe = None
        # Drain any stragglers that landed between ``wait_for_signal``
        # resolving and ``stop_capture`` firing so they don't leak into
        # the next session that reuses this provider instance.
        while not self._pulse_queue.empty():
            try:
                self._pulse_queue.get_nowait()
            except asyncio.QueueEmpty:
                break


__all__ = ["NativeIRCaptureProvider"]

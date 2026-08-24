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

# Importing ``homeassistant`` lazily keeps the capture package usable
# from pure-Python unit tests without a HA install. Anything that
# touches HA belongs behind ``_probe_receiver`` / ``async_start_capture``.
try:
    from homeassistant.exceptions import HomeAssistantError
except ImportError:  # pragma: no cover - exercised in tests via monkeypatch
    HomeAssistantError = None  # type: ignore[assignment,misc]

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
        return self._receiver.is_available and _is_ir_receiver(
            self._hass, self.receiver_entity_id
        )

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

        try:
            self._unsubscribe = await receiver.start_listening(_on_capture)
        except Exception as err:
            # ``infrared.async_subscribe_receiver`` raises
            # ``HomeAssistantError(translation_key="receiver_not_found")``
            # when the entity exists but isn't a registered
            # ``InfraredReceiverEntity``. Convert that and any other
            # HA-level failure into a friendly provider error so the
            # WS handler surfaces a real message instead of the raw
            # HA class name.
            if _is_unknown_receiver_error(err):
                raise CaptureProviderUnavailableError(
                    f"Receiver {self.receiver_entity_id!r} is not a registered "
                    "infrared receiver. Add an IR receiver entity to Home "
                    "Assistant or pick one configured for IR capture."
                ) from err
            raise
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


def _is_ir_receiver(hass: Any, receiver_entity_id: str) -> bool:
    """True when the entity is registered as an HA infrared receiver.

    HA's infrared platform keeps ``hass.data[infrared.DOMAIN]`` keyed
    by ``entity_id`` — only entities that implement
    ``InfraredReceiverEntity`` show up there. Anything else (a state
    that exists in another domain, a stale reference, etc.) returns
    ``False`` so the provider can refuse early instead of raising a
    raw ``HomeAssistantError`` mid-capture.
    """
    try:
        from homeassistant.components import infrared
    except ImportError:
        return False
    registry = hass.data.get(infrared.DOMAIN)
    if not isinstance(registry, dict):
        return False
    return receiver_entity_id in registry


def _is_unknown_receiver_error(err: BaseException) -> bool:
    """Detect HA's ``receiver_not_found`` error regardless of version.

    Older HA versions raise ``HomeAssistantError("receiver_not_found")``
    (or with the message embedded). Newer ones carry
    ``translation_key="receiver_not_found"``. We accept any of those
    so the wrapper keeps working across HA upgrades.
    """
    if HomeAssistantError is None or not isinstance(err, HomeAssistantError):
        return False
    translation_key = getattr(err, "translation_key", None)
    if translation_key == "receiver_not_found":
        return True
    # Fallback: the legacy message form is the translation key string
    # itself, surfaced through ``str(err)`` when no translation is set.
    return "receiver_not_found" in str(err)

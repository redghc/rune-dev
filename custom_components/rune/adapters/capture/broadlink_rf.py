"""Broadlink RF capture provider — drives the sweep + capture flow.

The orchestrator's
:class:`~custom_components.rune.adapters.capture.orchestrator.CaptureOrchestrator`
expects a :class:`CaptureProvider` with a one-shot
``start → wait → stop`` shape. Broadlink RF doesn't have a
push-subscription model like the IR platform — instead it exposes
two on-demand phases (:meth:`BroadlinkRFReceiver.sweep_frequency`
and :meth:`BroadlinkRFReceiver.capture_packet`) that the SPA's
"Learn" UX drives in sequence.

This adapter bridges that gap by folding the entire sweep + capture
flow into a single :meth:`async_wait_for_signal` invocation. The
user gets to see a single "capturing…" state while the backend runs
through the two phases; the orchestrator + WS handler stay
agnostic.

Unlike :class:`NativeIRCaptureProvider`, this provider needs a live
``device_api`` handle to the Broadlink device. ``hass`` alone can't
derive one from an ``entity_id`` — the integration's setup phase
binds each ``remote.broadlink_*`` entity to its concrete API
object. The WS handler currently passes ``device_api=None``; until
the integration wires that plumbing up, RF capture surfaces a
clear :class:`CaptureProviderUnavailableError` explaining what's
missing.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.rune.adapters.capture.providers import CaptureProvider
from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.domain.errors import (
    CaptureProviderUnavailableError,
)
from custom_components.rune.ports.receiver import CapturedPulse

if TYPE_CHECKING:
    from custom_components.rune.adapters.receivers.broadlink_rf import (
        BroadlinkRFReceiver,
    )

_LOGGER = logging.getLogger(__name__)


class BroadlinkRFCaptureProvider(CaptureProvider):
    """One-shot RF capture session bound to a single Broadlink receiver.

    Parameters
    ----------
    hass:
        Home Assistant instance. Accepted for interface parity with the
        IR provider; Broadlink operates directly on the device API.
    receiver_entity_id:
        The ``remote.broadlink_*`` entity to capture through.
    device_api:
        The live ``broadlink`` API object backing ``receiver_entity_id``.
        **Required** — without it the provider can't drive the
        sweep + capture flow. Pass ``None`` only when the caller wants
        a clear "not configured" error rather than a generic crash.

    The class is transport-fixed to RF: an RF receiver is identified
    by its ``remote.*`` domain and the Broadlink-only sweep+capture
    protocol. Adding other RF transports (Zigbee, MQTT) means a
    parallel provider class — keeping them separate avoids muddling
    the per-domain error reporting the WS handler surfaces.
    """

    transport = SignalTransport.RF
    name = "broadlink-rf"

    def __init__(
        self,
        hass: Any,
        receiver_entity_id: str,
        device_api: Any = None,
    ) -> None:
        self._hass = hass
        self.receiver_entity_id = receiver_entity_id
        self._device_api = device_api
        self._receiver: "BroadlinkRFReceiver | None" = None
        self._started = False
        self._result: CapturedPulse | None = None

    @property
    def is_available(self) -> bool:
        """True when the device API is bound and the entity is loaded.

        ``is_available`` for a Broadlink receiver isn't a clean state
        lookup like HA's IR registry — we accept "the API exists" as
        a proxy. The capture itself will surface a hardware error if
        the device went offline between this check and the actual
        sweep.
        """
        if not self.receiver_entity_id or self._device_api is None:
            return False
        try:
            from custom_components.rune.adapters.receivers.broadlink_rf import (
                BroadlinkRFReceiver,
            )
        except ImportError:  # pragma: no cover
            return False
        self._receiver = BroadlinkRFReceiver(
            self._hass, self.receiver_entity_id, self._device_api
        )
        return self._receiver.is_available

    async def async_start_capture(self, timeout_s: float) -> None:
        if not self.is_available:
            raise CaptureProviderUnavailableError(
                f"RF receiver {self.receiver_entity_id!r} is not available. "
                "Confirm the Broadlink device is online and that the "
                "RUNE integration has a live device_api handle for it."
            )
        # No subscription to install; ``async_wait_for_signal`` does
        # the sweep + capture inline.
        self._started = True

    async def async_wait_for_signal(self, timeout_s: float) -> CapturedPulse | None:
        """Run sweep + capture in one go; returns the captured pulse.

        Caches the result so a re-entry from the orchestrator's loop
        doesn't trigger a second sweep (which would surprise the
        user with two more "press and hold" prompts).
        """
        if not self._started:
            raise RuntimeError(
                "BroadlinkRFCaptureProvider.async_wait_for_signal called before "
                "async_start_capture"
            )
        if self._receiver is None:  # pragma: no cover - guarded by start
            raise CaptureProviderUnavailableError(
                "BroadlinkRFReceiver was not initialised"
            )
        if self._result is not None:
            return self._result

        # We swallow the per-phase errors from the underlying receiver
        # — they already carry helpful messages. The orchestrator
        # maps them onto capture-state transitions; we just return
        # ``None`` to mean "nothing captured within the timeout".
        try:
            self._result = await self._receiver.capture_with_sweep()
        except Exception as err:
            _LOGGER.warning(
                "Broadlink RF capture failed for %s: %s",
                self.receiver_entity_id,
                err,
            )
            self._result = None
        return self._result

    async def async_stop_capture(self) -> None:
        self._started = False
        # Nothing to unsubscribe — RF capture is on-demand.


__all__ = ["BroadlinkRFCaptureProvider"]

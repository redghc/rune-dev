"""Broadlink RF capture provider — drives the sweep + capture flow.

The orchestrator's
:class:`~custom_components.rune.adapters.capture.orchestrator.CaptureOrchestrator`
expects a :class:`CaptureProvider` with a one-shot
``start → wait → stop`` shape. Broadlink RF doesn't have a
push-subscription model like the IR platform — instead it exposes
two on-demand phases (:meth:`BroadlinkRFReceiver.sweep_frequency`
and :meth:`BroadlinkRFReceiver.capture_packet`) that the SPA's
"Learn" UX drives in sequence.

This adapter bridges that gap by folding the sweep + capture flow
into a single :meth:`async_wait_for_signal` invocation. The user
gets to see a single "capturing…" state while the backend runs
through the two phases; the orchestrator + WS handler stay
agnostic.

A second mode — **direct capture** — listens at a preset frequency
without sweeping. Used for remotes that send very short bursts
the sweep can't lock onto (Mercator FRM97 and similar). The
:attr:`direct` flag and :attr:`frequency_hz` value are forwarded
straight to :meth:`BroadlinkRFReceiver.capture_direct`.

Unlike :class:`NativeIRCaptureProvider`, this provider needs a live
``BroadlinkDevice`` handle to the actual hardware. ``hass`` alone
can't derive one from an ``entity_id`` — the Broadlink integration's
setup phase binds each ``remote.broadlink_*`` entity to its concrete
device object. We look it up at provider-construction time via
:func:`adapters.broadlink_devices.find_rf_device_for_entity`.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.rune.adapters.broadlink_devices import (
    find_rf_device_for_entity,
)
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
        Home Assistant instance. Used to look up the BroadlinkDevice
        that owns ``receiver_entity_id``.
    receiver_entity_id:
        The ``remote.broadlink_*`` entity to capture through.
    direct:
        When ``True``, skip the sweep phase and listen at
        ``frequency_hz`` directly. Default ``False`` (full sweep
        + capture).
    frequency_hz:
        Carrier frequency for direct capture, in Hz. Ignored unless
        ``direct=True``. Defaults to 433.92 MHz when not provided.

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
        *,
        direct: bool = False,
        frequency_hz: int | None = None,
    ) -> None:
        self._hass = hass
        self.receiver_entity_id = receiver_entity_id
        self._direct = direct
        self._frequency_hz = frequency_hz
        # ``_device`` is resolved lazily in :meth:`is_available` /
        # :meth:`async_start_capture` so the cost of walking the
        # Broadlink registry is only paid when the user actually
        # triggers a learn session.
        self._device: Any = None
        self._receiver: "BroadlinkRFReceiver | None" = None
        self._started = False
        self._result: CapturedPulse | None = None

    def _resolve_device(self) -> Any:
        if self._device is None:
            self._device = find_rf_device_for_entity(
                self._hass, self.receiver_entity_id
            )
        return self._device

    @property
    def is_available(self) -> bool:
        """True when a live Broadlink device is bound to this entity.

        Resolves the device lazily so the sniffer engine's per-tick
        probe stays cheap. The first miss surfaces a clear error
        with actionable guidance for the user.
        """
        device = self._resolve_device()
        if device is None:
            return False
        from custom_components.rune.adapters.receivers.broadlink_rf import (
            BroadlinkRFReceiver,
        )

        self._receiver = BroadlinkRFReceiver(
            self._hass, self.receiver_entity_id, device
        )
        return self._receiver.is_available

    async def async_start_capture(self, timeout_s: float) -> None:
        device = self._resolve_device()
        if device is None:
            raise CaptureProviderUnavailableError(
                f"No Broadlink device found for {self.receiver_entity_id!r}. "
                "Make sure the entity belongs to an RF-capable Broadlink "
                "device (RM Pro / RM4 Pro) set up in the Broadlink "
                "integration."
            )
        # No subscription to install — ``async_wait_for_signal``
        # runs sweep + capture inline.
        self._started = True

    async def async_wait_for_signal(self, timeout_s: float) -> CapturedPulse | None:
        """Run sweep + capture (or direct capture) in one go.

        Caches the result so a re-entry from the orchestrator's
        polling loop doesn't trigger a second sweep — which would
        surprise the user with two more "press and hold" prompts.
        """
        if not self._started:
            raise RuntimeError(
                "BroadlinkRFCaptureProvider.async_wait_for_signal called before "
                "async_start_capture"
            )
        if self._receiver is None:
            self._receiver = self._build_receiver()
        if self._result is not None:
            return self._result

        try:
            if self._direct:
                assert self._frequency_hz is not None
                self._result = await self._receiver.capture_direct(self._frequency_hz)
            else:
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

    def _build_receiver(self) -> "BroadlinkRFReceiver":
        from custom_components.rune.adapters.receivers.broadlink_rf import (
            BroadlinkRFReceiver,
        )

        device = self._resolve_device()
        if device is None:
            # ``async_start_capture`` already raised; this is just
            # defence-in-depth for any caller that skips the probe.
            raise CaptureProviderUnavailableError(
                f"No Broadlink device bound for {self.receiver_entity_id!r}"
            )
        return BroadlinkRFReceiver(self._hass, self.receiver_entity_id, device)


__all__ = ["BroadlinkRFCaptureProvider"]

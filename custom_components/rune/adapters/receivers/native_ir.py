"""Native IR receiver — subscribes to HA's ``infrared`` platform.

For any entity that implements
:class:`homeassistant.components.infrared.InfraredReceiverEntity`
(ESPHome IR receivers since 2026.6, SMLIGHT since 2026.7, any future
adopter), this adapter hooks ``infrared.async_subscribe_receiver``
and translates each ``InfraredReceivedSignal`` into RUNE's
:class:`CapturedPulse` format.

The subscription callback runs on HA's event loop; we hand the
captured pulse to the user-supplied callback as a fire-and-forget
coroutine — the sniffer engine is responsible for back-pressure.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from custom_components.rune.domain.enums import (
    ReceiverSourceKind,
    SignalCategory,
    SignalEncoding,
    SignalTransport,
)
from custom_components.rune.domain.models import UnknownSignal, new_id
from custom_components.rune.domain.time import utcnow_iso
from custom_components.rune.ports.receiver import (
    CaptureCallback,
    CapturedPulse,
    ReceiverPort,
)

if TYPE_CHECKING:
    from homeassistant.components.infrared import InfraredReceivedSignal

_LOGGER = logging.getLogger(__name__)


class NativeIRReceiver(ReceiverPort):
    """Subscribes to one ``InfraredReceiverEntity`` via the HA helper."""

    transport = SignalTransport.IR
    source_kind = ReceiverSourceKind.NATIVE_INFRARED

    def __init__(self, hass: Any, receiver_entity_id: str) -> None:
        self._hass = hass
        self.receiver_entity_id = receiver_entity_id
        self._unsubscribe: Callable[[], None] | None = None

    @property
    def is_available(self) -> bool:
        state = self._hass.states.get(self.receiver_entity_id)
        return state is not None and state.state != "unavailable"

    async def start_listening(self, on_capture: CaptureCallback) -> Callable[[], None]:
        try:
            from homeassistant.components import infrared
        except ImportError as err:
            raise RuntimeError(
                "homeassistant.components.infrared is unavailable on this HA version"
            ) from err

        def _on_signal(signal: InfraredReceivedSignal) -> None:
            # Schedule the callback on the event loop. We don't await
            # here — the subscribe API is synchronous and returning
            # early would let the next signal arrive before our async
            # matcher finishes. The matcher itself is built to handle
            # out-of-order delivery.
            self._hass.async_create_task(_dispatch(signal, self.receiver_entity_id, on_capture))

        self._unsubscribe = infrared.async_subscribe_receiver(
            self._hass,
            self.receiver_entity_id,
            _on_signal,
        )

        def _stop() -> None:
            if self._unsubscribe is not None:
                self._unsubscribe()
                self._unsubscribe = None

        return _stop

    async def stop_listening(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None


async def _dispatch(
    signal: InfraredReceivedSignal,
    receiver_entity_id: str,
    on_capture: CaptureCallback,
) -> None:
    """Translate an HA InfraredReceivedSignal to a RUNE CapturedPulse.

    The native helper delivers raw timings (signed alternating
    microseconds) and a modulation frequency. We don't decode the
    protocol here — that's the matcher's job in
    :mod:`custom_components.rune.domain.signal.normalize`.
    """
    timings = tuple(int(t) for t in signal.timings)
    captured = CapturedPulse(
        receiver_entity_id=receiver_entity_id,
        signal_category=SignalCategory(
            transport=SignalTransport.IR,
            encoding=SignalEncoding.RAW_TIMINGS,
            carrier_frequency_hz=int(signal.modulation) if signal.modulation else 38_000,
        ),
        raw_timings=timings,
    )
    await on_capture(captured)


def build_unknown_signal_from_capture(captured: CapturedPulse) -> UnknownSignal:
    """Build an UnknownSignal record from a captured pulse.

    Used by the sniffer engine after the matcher fails to attach the
    capture to an existing signal — we mint a new row from the raw
    timings alone (identity-tier-3) and the sniffer upgrades it
    later when a decoded identity arrives.
    """
    return UnknownSignal(
        id=new_id(),
        fingerprint="",  # filled in by the matcher / normalizer
        signal_category=captured.signal_category,
        raw_timings=captured.raw_timings,
        first_seen=utcnow_iso(),
        last_seen=utcnow_iso(),
        hit_count=1,
        protocol_label=captured.protocol_label,
        code_hex=captured.code_hex,
    )

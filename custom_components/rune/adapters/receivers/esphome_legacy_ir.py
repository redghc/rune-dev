"""ESPHome legacy IR receiver.

Fallback path for HA installations where ESPHome IR receivers are not
yet exposing :class:`homeassistant.components.infrared.InfraredReceiverEntity`.
Older setups use an ESPHome YAML bridge:

    remote_receiver:
      pin: GPIO14
      tolerance: 25%
      on_pronto:
        then:
          - homeassistant.event:
              event: esphome.remote_received
              data:
                pronto: !lambda 'return x;'

The receiver subscribes to the ``esphome.remote_received`` event on
the HA bus and decodes the Pronto hex string back into raw timings.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from custom_components.rune.domain.encoding.pronto import pronto_hex_to_raw_timings
from custom_components.rune.domain.enums import (
    ReceiverSourceKind,
    SignalCategory,
    SignalEncoding,
    SignalTransport,
)
from custom_components.rune.ports.receiver import (
    CaptureCallback,
    CapturedPulse,
    ReceiverPort,
)

if TYPE_CHECKING:
    from homeassistant.core import Event

_LOGGER = logging.getLogger(__name__)


# ESPHome bridge event name (legacy HA < 2026.6 path).
LEGACY_ESPHOME_IR_EVENT = "esphome.remote_received"


class ESPHomeLegacyIRReceiver(ReceiverPort):
    """Subscribes to ``esphome.remote_received`` for one receiver."""

    transport = SignalTransport.IR
    source_kind = ReceiverSourceKind.ESPHOME_LEGACY_IR

    def __init__(self, hass: Any, receiver_entity_id: str) -> None:
        self._hass = hass
        self.receiver_entity_id = receiver_entity_id
        self._unsub_event: Callable[[], None] | None = None

    @property
    def is_available(self) -> bool:
        # The bridge event is always available (HA core) — we just
        # can't tell whether the underlying ESPHome node is online.
        return True

    async def start_listening(self, on_capture: CaptureCallback) -> Callable[[], None]:
        def _on_event(event: Event) -> None:
            data = event.data or {}
            # ESPHome's bridge event carries `pronto` (the Pronto hex
            # string) and an optional `entity_id`. We filter by entity.
            event_entity_id = data.get("entity_id")
            if event_entity_id is not None and event_entity_id != self.receiver_entity_id:
                return
            pronto_hex = data.get("pronto") or data.get("command")
            if not pronto_hex:
                return
            try:
                timings = pronto_hex_to_raw_timings(pronto_hex)
            except ValueError as err:
                _LOGGER.warning("rune: failed to decode pronto hex: %s", err)
                return
            self._hass.async_create_task(
                _dispatch(timings, self.receiver_entity_id, on_capture)
            )

        self._unsub_event = self._hass.bus.async_listen(LEGACY_ESPHOME_IR_EVENT, _on_event)

        def _stop() -> None:
            if self._unsub_event is not None:
                self._unsub_event()
                self._unsub_event = None

        return _stop

    async def stop_listening(self) -> None:
        if self._unsub_event is not None:
            self._unsub_event()
            self._unsub_event = None


async def _dispatch(
    timings: list[int],
    receiver_entity_id: str,
    on_capture: CaptureCallback,
) -> None:
    captured = CapturedPulse(
        receiver_entity_id=receiver_entity_id,
        signal_category=SignalCategory(
            transport=SignalTransport.IR,
            encoding=SignalEncoding.RAW_TIMINGS,
            carrier_frequency_hz=38_000,
        ),
        raw_timings=tuple(int(t) for t in timings),
    )
    await on_capture(captured)

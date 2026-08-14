"""Broadlink RF receiver — the two-phase sweep + capture learn flow.

RF capture has no native subscription model (unlike IR's ``async_subscribe_receiver``).
The Broadlink RM Pro / RM4 Pro exposes two-step learning:

1. **Sweep**: ``device.api.sweep_frequency`` polls the receiver while
   the user holds a button, until ``device.api.check_frequency`` reports
   a carrier was found.
2. **Capture**: ``device.api.find_rf_packet`` locks onto the carrier
   and ``device.api.check_data`` returns the raw packet bytes.

This adapter wraps both phases behind the :class:`ReceiverPort` API.
Because RF capture is on-demand (no continuous stream), the adapter
implements ``start_listening`` as an immediate no-op that returns a
stop callable, and exposes :meth:`capture_now` for the capture orchestrator
to invoke per-button.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

try:
    from broadlink.exceptions import ReadError, StorageError
except ImportError:  # broadlink not installed (pure dev env / CI without HA deps)
    ReadError = OSError  # type: ignore[assignment,misc]
    StorageError = OSError  # type: ignore[assignment,misc]

from custom_components.rune.const import LEARNING_TIMEOUT_S
from custom_components.rune.domain.encoding.broadlink import (
    decode_broadlink_rf_packet,
)
from custom_components.rune.domain.enums import (
    ReceiverSourceKind,
    SignalCategory,
    SignalEncoding,
    SignalTransport,
)
from custom_components.rune.domain.errors import (
    CaptureError,
    CaptureProviderUnavailableError,
    CaptureTimeoutError,
)
from custom_components.rune.domain.models import UnknownSignal, new_id
from custom_components.rune.domain.time import utcnow_iso
from custom_components.rune.ports.receiver import (
    CaptureCallback,
    CapturedPulse,
    ReceiverPort,
)

_LOGGER = logging.getLogger(__name__)


class BroadlinkRFReceiver(ReceiverPort):
    """Drives the Broadlink two-phase RF learn flow.

    The ``hass`` arg is unused by this adapter (Broadlink operates
    directly on the device API); it's accepted for interface parity
    with the other adapters.
    """

    transport = SignalTransport.RF
    source_kind = ReceiverSourceKind.BROADLINK_RF

    def __init__(self, hass: Any, receiver_entity_id: str, device_api: Any) -> None:
        self._hass = hass
        self.receiver_entity_id = receiver_entity_id
        self._device_api = device_api

    @property
    def is_available(self) -> bool:
        # The device is reachable if the underlying API responds.
        # No cheap way to ping from here; the sniffer's health loop
        # uses the same check.
        return self._device_api is not None

    async def start_listening(self, on_capture: CaptureCallback) -> callable:
        """RF capture is on-demand; no subscription to install.

        The capture orchestrator invokes :meth:`capture_now` directly
        when the user triggers a learn session. We still return an
        unsubscribe callable for symmetry with continuous receivers.
        """

        def _stop() -> None:
            # Nothing to do — capture is per-invocation.
            return

        return _stop

    async def stop_listening(self) -> None:
        # Nothing to tear down.
        return

    # ------------------------------------------------------------------
    # Capture flow (invoked by the capture orchestrator)
    # ------------------------------------------------------------------

    async def sweep_frequency(self) -> float:
        """Phase 1: sweep for the carrier while the user holds a button.

        Returns the detected frequency in MHz. Raises
        :class:`CaptureTimeoutError` when nothing is found within
        ``LEARNING_TIMEOUT_S``.
        """
        if self._device_api is None or not hasattr(self._device_api, "sweep_frequency"):
            raise CaptureProviderUnavailableError(
                f"Device API for {self.receiver_entity_id} does not support sweep"
            )
        try:
            await self._device_api.sweep_frequency()
            _LOGGER.warning(
                "rune: Broadlink RF sweep started - PRESS AND HOLD the remote button now"
            )
            deadline = time.monotonic() + LEARNING_TIMEOUT_S
            while time.monotonic() < deadline:
                await asyncio.sleep(1)
                is_found, frequency = await self._device_api.check_frequency()
                if is_found:
                    _LOGGER.warning("rune: RF carrier detected at %.3f MHz", frequency)
                    return float(frequency)
            await self._device_api.cancel_sweep_frequency()
            raise CaptureTimeoutError(
                f"No RF frequency detected within {LEARNING_TIMEOUT_S:.0f}s"
            )
        except CaptureTimeoutError:
            raise
        except (ReadError, StorageError, OSError) as err:
            raise CaptureError(f"Broadlink RF sweep failed: {err}") from err

    async def capture_packet(self, frequency_mhz: float | None = None) -> dict[str, Any]:
        """Phase 2: capture an RF packet at the locked (or pre-set) frequency.

        Returns ``{"b64", "timings", "repeat", "length"}``. Raises
        :class:`CaptureTimeoutError` on timeout, :class:`CaptureError`
        on hardware failure.
        """
        if self._device_api is None or not hasattr(self._device_api, "find_rf_packet"):
            raise CaptureProviderUnavailableError(
                f"Device API for {self.receiver_entity_id} does not support packet capture"
            )
        try:
            await self._device_api.find_rf_packet(frequency_mhz)
            if frequency_mhz:
                _LOGGER.warning(
                    "rune: listening at %.3f MHz - PRESS the button once", frequency_mhz
                )
            else:
                _LOGGER.warning(
                    "rune: locked on - RELEASE, then PRESS the same button again"
                )
            deadline = time.monotonic() + LEARNING_TIMEOUT_S
            while time.monotonic() < deadline:
                await asyncio.sleep(1)
                try:
                    code = await self._device_api.check_data()
                except (ReadError, StorageError):
                    continue  # nothing captured yet
                from base64 import b64encode
                timings, repeat = decode_broadlink_rf_packet(code)
                _LOGGER.warning(
                    "rune: captured %d pulses (raw repeat=%d, ignored on resend)",
                    len(timings),
                    repeat,
                )
                return {
                    "b64": b64encode(code).decode("utf8"),
                    "timings": timings,
                    "repeat": repeat,
                    "length": len(timings),
                }
            raise CaptureTimeoutError(
                f"No RF code received within {LEARNING_TIMEOUT_S:.0f}s"
            )
        except CaptureTimeoutError:
            raise
        except (OSError, ValueError) as err:
            raise CaptureError(f"Broadlink RF capture failed: {err}") from err

    async def capture_with_sweep(self) -> CapturedPulse:
        """Convenience: full sweep+capture flow returning a CapturedPulse.

        Used by the capture orchestrator's "Learn button" UX.
        """
        frequency_mhz = await self.sweep_frequency()
        await asyncio.sleep(1)
        packet = await self.capture_packet(frequency_mhz)
        frequency_hz = int(frequency_mhz * 1_000_000)
        return CapturedPulse(
            receiver_entity_id=self.receiver_entity_id,
            signal_category=SignalCategory(
                transport=SignalTransport.RF,
                encoding=SignalEncoding.RAW_TIMINGS,
                carrier_frequency_hz=frequency_hz,
            ),
            raw_timings=tuple(packet["timings"]),
            protocol_label=None,
            code_hex=None,
        )


def build_unknown_signal_from_packet(
    *,
    packet: dict[str, Any],
    receiver_entity_id: str,
    frequency_hz: int,
) -> UnknownSignal:
    """Mint an UnknownSignal from a captured RF packet.

    Convenience for the capture orchestrator: avoids the boilerplate
    of constructing every UnknownSignal field by hand.
    """
    return UnknownSignal(
        id=new_id(),
        fingerprint="",  # filled by normalizer
        signal_category=SignalCategory(
            transport=SignalTransport.RF,
            encoding=SignalEncoding.RAW_TIMINGS,
            carrier_frequency_hz=frequency_hz,
        ),
        raw_timings=tuple(packet["timings"]),
        first_seen=utcnow_iso(),
        last_seen=utcnow_iso(),
        hit_count=1,
    )


# Re-export for tests that need to construct an UnknownSignal without
# pulling the field defaults apart.
__all__ = [
    "BroadlinkRFReceiver",
    "build_unknown_signal_from_packet",
]

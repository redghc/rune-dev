"""Broadlink RF receiver — the two-phase sweep + capture learn flow.

RF capture has no native subscription model (unlike IR's
``async_subscribe_receiver``). The Broadlink RM Pro / RM4 Pro
exposes two-step learning:

1. **Sweep**: ``device.api.sweep_frequency`` polls the receiver
   while the user holds a button, until ``device.api.check_frequency``
   reports a carrier was found.
2. **Capture**: ``device.api.find_rf_packet`` locks onto the carrier
   and ``device.api.check_data`` returns the raw packet bytes.

A third mode — **direct capture** — skips the sweep entirely and
listens at a preset frequency (433.92 / 315 / 868 / 915 MHz). It
exists for remotes that send very short bursts the sweep can't lock
onto (Mercator FRM97 and similar). The user picks the frequency
explicitly in the SPA's Learn dialog.

This adapter wraps all three flows behind the :class:`ReceiverPort`
API. Because RF capture is on-demand (no continuous stream), the
adapter implements ``start_listening`` as an immediate no-op that
returns a stop callable, and exposes :meth:`capture_with_sweep` /
:meth:`capture_direct` for the capture orchestrator to invoke
per-button.

The ``hass`` arg is accepted for interface parity but unused; the
adapter talks to the Broadlink integration through a pre-resolved
``device`` object whose ``async_request(api.method)`` coroutine
wrapper handles the integration's locking. Calling the synchronous
API directly can race with concurrent sends.
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

    Parameters
    ----------
    hass:
        Home Assistant instance (unused; kept for interface parity
        with the IR receiver adapters).
    receiver_entity_id:
        The ``remote.broadlink_*`` entity the capture is bound to.
    device:
        The full ``BroadlinkDevice`` wrapper from the Broadlink
        integration. We call ``device.async_request(api.method)`` —
        the integration's coroutine wrapper handles locking and
        async dispatch around the synchronous Broadlink SDK calls.
        Passing only the bare ``device.api`` would skip that safety
        net and is not supported here.

        Pass ``None`` only when you want the provider to surface a
        clear "no Broadlink device bound" error rather than crash.
    """

    transport = SignalTransport.RF
    source_kind = ReceiverSourceKind.BROADLINK_RF

    def __init__(
        self,
        hass: Any,
        receiver_entity_id: str,
        device: Any,
    ) -> None:
        self._hass = hass
        self.receiver_entity_id = receiver_entity_id
        self._device = device

    @property
    def is_available(self) -> bool:
        """True when a live Broadlink device is bound.

        Cheap, in-memory check: we don't ping the device; the actual
        sweep / capture surfaces a hardware error if the device went
        offline between this probe and the call.
        """
        return self._device is not None and hasattr(
            getattr(self._device, "api", None), "sweep_frequency"
        )

    @property
    def _api(self) -> Any:
        """The Broadlink API object on the bound device.

        Raises :class:`CaptureProviderUnavailableError` if no device
        is bound — keeps the ``self._api.foo()`` call sites readable
        without scattering ``if self._device is None`` checks.
        """
        if self._device is None or not hasattr(self._device, "api"):
            raise CaptureProviderUnavailableError(
                f"No Broadlink device bound for {self.receiver_entity_id!r}. "
                "The WS handler couldn't resolve the device — make sure "
                "the entity belongs to a Broadlink RF-capable unit."
            )
        return self._device.api

    async def _request(self, method: Any, *args: Any) -> Any:
        """Invoke a Broadlink API method through ``async_request``.

        Every Broadlink SDK call is synchronous; the integration's
        ``async_request`` coroutine wrapper schedules them on its
        own loop and serialises concurrent sends. Calling
        ``self._api.method()`` directly can race with concurrent
        sends or block the HA event loop.
        """
        if not hasattr(self._device, "async_request"):
            raise CaptureProviderUnavailableError(
                f"Broadlink device for {self.receiver_entity_id!r} is missing "
                "the async_request wrapper — older Broadlink integration?"
            )
        return await self._device.async_request(method, *args)

    async def start_listening(self, on_capture: CaptureCallback) -> callable:
        """RF capture is on-demand; no subscription to install.

        The capture orchestrator invokes :meth:`capture_with_sweep` /
        :meth:`capture_direct` directly when the user triggers a
        learn session. We still return an unsubscribe callable for
        symmetry with continuous receivers.
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
        api = self._api
        if not hasattr(api, "sweep_frequency"):
            raise CaptureProviderUnavailableError(
                f"Device API for {self.receiver_entity_id} does not support sweep"
            )
        try:
            await self._request(api.sweep_frequency)
            _LOGGER.warning(
                "rune: Broadlink RF sweep started - PRESS AND HOLD the remote button now"
            )
            deadline = time.monotonic() + LEARNING_TIMEOUT_S
            while time.monotonic() < deadline:
                await asyncio.sleep(1)
                is_found, frequency = await self._request(api.check_frequency)
                if is_found:
                    _LOGGER.warning("rune: RF carrier detected at %.3f MHz", frequency)
                    return float(frequency)
            await self._request(api.cancel_sweep_frequency)
            raise CaptureTimeoutError(
                f"No RF frequency detected within {LEARNING_TIMEOUT_S:.0f}s"
            )
        except CaptureTimeoutError:
            raise
        except (ReadError, StorageError, OSError) as err:
            raise CaptureError(f"Broadlink RF sweep failed: {err}") from err

    async def capture_packet(self, frequency_mhz: float | None = None) -> dict[str, Any]:
        """Phase 2 (or direct): capture an RF packet at the locked /
        pre-set frequency.

        Returns ``{"b64", "timings", "repeat", "length"}``. Raises
        :class:`CaptureTimeoutError` on timeout, :class:`CaptureError`
        on hardware failure.
        """
        api = self._api
        if not hasattr(api, "find_rf_packet"):
            raise CaptureProviderUnavailableError(
                f"Device API for {self.receiver_entity_id} does not support packet capture"
            )
        try:
            await self._request(api.find_rf_packet, frequency_mhz)
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
                    code = await self._request(api.check_data)
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
        Carries the raw ``b64`` packet on the returned pulse so the
        SPA can build a resendable ``b64:<payload>`` PulseCommand
        without needing the receiver's device API on the wire side.
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
            b64_packet=packet["b64"],
        )

    async def capture_direct(self, frequency_hz: int) -> CapturedPulse:
        """Direct capture: listen at ``frequency_hz`` with no sweep.

        For remotes that send very short bursts the Broadlink
        frequency sweep can't lock onto (Mercator FRM97 and similar).
        The user picks the carrier explicitly in the SPA's Learn
        dialog; we listen at that frequency and capture the next
        packet the receiver sees.

        Raises :class:`CaptureTimeoutError` when nothing arrives
        within ``LEARNING_TIMEOUT_S``.
        """
        frequency_mhz = frequency_hz / 1_000_000.0
        packet = await self.capture_packet(frequency_mhz)
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
            b64_packet=packet["b64"],
        )

    async def capture_ir(self) -> CapturedPulse:
        """Learn an IR code with the Broadlink's built-in receiver.

        The HA Broadlink integration exposes IR *emitter* entities
        (``infrared.*``) but not the hardware's IR receiver, so
        ``infrared.async_subscribe_receiver`` can't drive a learn
        session for these devices. The SDK's classic IR learn flow
        works regardless: ``enter_learning()`` arms the receiver,
        then polling ``check_data()`` returns the captured packet.

        Single-phase (no sweep, no carrier) — the user just presses
        the remote button once while we listen.

        Raises :class:`CaptureTimeoutError` when nothing arrives
        within ``LEARNING_TIMEOUT_S``.
        """
        from base64 import b64encode

        from custom_components.rune.domain.encoding.broadlink import (
            decode_broadlink_ir_packet,
        )

        api = self._api
        if not hasattr(api, "enter_learning"):
            raise CaptureProviderUnavailableError(
                f"Device API for {self.receiver_entity_id} does not support "
                "IR learning (no enter_learning)"
            )
        try:
            await self._request(api.enter_learning)
            _LOGGER.warning(
                "rune: Broadlink IR learning started - PRESS the remote button now"
            )
            deadline = time.monotonic() + LEARNING_TIMEOUT_S
            while time.monotonic() < deadline:
                await asyncio.sleep(1)
                try:
                    code = await self._request(api.check_data)
                except (ReadError, StorageError):
                    continue  # nothing captured yet
                timings, _repeat = decode_broadlink_ir_packet(code)
                _LOGGER.warning(
                    "rune: captured %d IR pulses via Broadlink SDK",
                    len(timings),
                )
                return CapturedPulse(
                    receiver_entity_id=self.receiver_entity_id,
                    signal_category=SignalCategory.default_ir(),
                    raw_timings=tuple(timings),
                    protocol_label=None,
                    code_hex=None,
                    b64_packet=b64encode(code).decode("utf8"),
                )
            raise CaptureTimeoutError(
                f"No IR code received within {LEARNING_TIMEOUT_S:.0f}s"
            )
        except CaptureTimeoutError:
            raise
        except (OSError, ValueError) as err:
            raise CaptureError(f"Broadlink IR learning failed: {err}") from err


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

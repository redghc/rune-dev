"""Common helpers for transmitter adapters.

Every adapter:

1. Reads the ``PulsePayload`` for a command.
2. Applies the transmit-boundary transforms (``trim_idle`` +
   ``apply_bounded_terminator``).
3. Encodes the result into whatever shape the hardware wants.
4. Calls the HA service / helper.

Steps 2 and 3 are shared. This module owns step 2 plus the
encoder-dispatch table.

No Home Assistant imports here — encoding is a pure concern. Hardware-
specific encoding helpers live in :mod:`custom_components.rune.domain.encoding`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from custom_components.rune.domain.encoding.timing import (
    apply_bounded_terminator,
    trim_idle,
)
from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.domain.models import PulseCommand, PulsePayload


@dataclass(frozen=True)
class PreparedTimings:
    """A pulse payload after the transmit-boundary transforms.

    ``raw_timings`` is the trimmed+terminated list — what the
    transmitter hands to the hardware. ``carrier_frequency_hz``
    mirrors the source device's frequency for RF; for IR it stays at
    the device's learned carrier (typically 38 kHz).
    """

    raw_timings: list[int]
    carrier_frequency_hz: int
    repeat_count: int
    send_count: int


def prepare_timings(command: PulseCommand) -> PreparedTimings | None:
    """Return the transmit-boundary form of ``command``, or ``None`` if empty.

    - ``trim_idle`` drops the learning-timeout noise that receivers
      appended on capture.
    - ``apply_bounded_terminator`` guarantees the array ends on a
      space within ``TERMINATOR_SPACE_US`` (HAIR's transmission rule).

    Returns ``None`` for payloads with no raw timings — adapters that
    know how to send ``decoded_hex`` or ``base64_packet`` (Broadlink,
    ESPHome) handle those directly and skip this path.
    """
    if command.payload.raw_timings is None:
        return None
    trimmed = trim_idle(list(command.payload.raw_timings))
    bounded = apply_bounded_terminator(trimmed)
    return PreparedTimings(
        raw_timings=bounded,
        carrier_frequency_hz=command.signal_category.carrier_frequency_hz,
        repeat_count=command.payload.repeat_count,
        send_count=command.payload.send_count,
    )


def select_payload(command: PulseCommand) -> PulsePayload:
    """Return the payload to send — same instance, but never None.

    Adapters that don't know how to send every encoding variant should
    inspect ``payload.raw_timings`` first; if it's None they should
    raise :class:`UnsupportedHardwareError` (from the domain errors
    module) rather than try to send garbage.
    """
    return command.payload


def ha_carrier_from_signal_category(transport: SignalTransport, frequency_hz: int) -> int:
    """Return the carrier frequency expected by HA's helpers.

    HA's native infrared helpers take the carrier in Hz. RF helpers
    use the frequency embedded in the command object — no separate
    carrier arg.
    """
    if frequency_hz <= 0:
        raise ValueError(f"Carrier frequency must be positive, got {frequency_hz}")
    return frequency_hz


def build_known_hardware_keys() -> dict[str, Any]:
    """Return the registry of supported hardware identifiers.

    Useful for diagnostics: lets the integration tell users what
    hardware is recognized when a config flow sees an unknown entity.
    """
    return {
        "infrared_domain": "native_infrared",
        "radio_frequency_domain": "native_radio_frequency",
        "broadlink_domain": "broadlink",
        "esphome_domain": "esphome",
    }

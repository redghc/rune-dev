"""Broadlink IR/RF packet encoding and decoding.

Two flows:

- IR: Pronto timings → LIRC ticks → Broadlink pulse buffer → base64.
- RF: captured Broadlink pulse packet → signed alternating microsecond
  timings (so the same raw-timings pipeline works for both IR and RF).

The IR constants (``269 / 8192``) come from SmartIR's ``Helper.lirc2broadlink``,
bench-verified against a real RM Pro. The RF tick constant
(``BROADLINK_RF_TICK_US`` in ``const.py``) comes from rf_fan's
``_TICK_US``.
"""
from __future__ import annotations

import struct
from base64 import b64encode

from custom_components.rune.const import BROADLINK_RF_TICK_US


class BroadlinkFormatError(ValueError):
    """Raised when a Broadlink packed payload is malformed."""


# ---------------------------------------------------------------------------
# IR: LIRC ticks ⇄ Broadlink packed buffer
# ---------------------------------------------------------------------------

def lirc_to_broadlink(pulses: list[int]) -> bytearray:
    """Convert LIRC integer pulse widths to a Broadlink pulse buffer.

    Each input is a tick count that gets rescaled by the Broadlink IR
    constant (``269 / 8192``). Pulses shorter than 256 ticks pack into
    one byte; longer pulses emit a ``0x00`` escape followed by a
    big-endian uint16.
    """
    array = bytearray()
    for pulse in pulses:
        tick = max(0, round(pulse * 269 / 8192))
        if tick < 256:
            array += struct.pack(">B", tick)
        else:
            array += bytearray([0x00])
            array += struct.pack(">H", tick)
    return array


def broadlink_to_lirc(buffer: bytes) -> list[int]:
    """Inverse of :func:`lirc_to_broadlink`.

    A ``0x00`` escape byte is followed by a big-endian uint16 tick
    count; any other byte is itself the tick count.
    """
    pulses: list[int] = []
    index = 0
    while index < len(buffer):
        byte = buffer[index]
        if byte == 0x00 and index + 2 < len(buffer):
            tick = (buffer[index + 1] << 8) | buffer[index + 2]
            pulses.append(round(tick * 8192 / 269))
            index += 3
        else:
            pulses.append(round(byte * 8192 / 269))
            index += 1
    return pulses


def broadlink_to_base64(buffer: bytes) -> str:
    """Encode a Broadlink packed payload as base64.

    The output is the canonical form that the ``remote.send_command``
    service expects when ``commands`` is supplied as ``"b64:<payload>"``.
    """
    return b64encode(buffer).decode("utf-8")


# ---------------------------------------------------------------------------
# RF: decode captured Broadlink RF pulse packet
# ---------------------------------------------------------------------------
def decode_broadlink_rf_packet(packet: bytes) -> tuple[list[int], int]:
    """Decode a Broadlink RF pulse packet into signed alternating microseconds.

    Packet layout (matches ``broadlink.radio_frequency.encode_rf_packet``):

        byte 0        type byte (0xB2/0xD7 for 433 MHz, 0xB4 for 315 MHz)
        byte 1        repeat count
        bytes 2..3    payload length, little-endian, counted from byte 4
        bytes 4..     pulses (one byte per tick, or 0x00 + 2-byte big-endian
                      tick count for pulses of 256 ticks or more)

    Returns ``(timings, repeat_count)``. Even indices are marks
    (positive), odd indices are spaces (negative) — the format
    ``PulsePayload.raw_timings`` expects.
    """
    if len(packet) < 4:
        raise BroadlinkFormatError(
            f"RF packet too short: {len(packet)} bytes (need at least 4)"
        )
    repeat_count = packet[1]
    length = packet[2] | (packet[3] << 8)
    pulses = packet[4 : 4 + length]

    timings: list[int] = []
    index = 0
    while index < len(pulses):
        if pulses[index] == 0x00 and index + 2 < len(pulses):
            ticks = (pulses[index + 1] << 8) | pulses[index + 2]
            index += 3
        else:
            ticks = pulses[index]
            index += 1
        microseconds = round(ticks * BROADLINK_RF_TICK_US)
        if len(timings) % 2 == 0:
            timings.append(abs(microseconds))
        else:
            timings.append(-abs(microseconds))
    return timings, repeat_count


def decode_broadlink_ir_packet(packet: bytes) -> tuple[list[int], int]:
    """Decode a learned Broadlink IR packet into signed alternating microseconds.

    A learned IR code from ``device.check_data()`` carries the same
    4-byte header shape as the RF packet (type byte — 0x26 on RM4,
    0xB2-era on RM3 — repeat count, little-endian payload length)
    followed by packed IR ticks. The IR tick constant differs from
    RF: SmartIR's ``269 / 8192`` ratio (≈ 30.46 µs per tick), the
    same one :func:`lirc_to_broadlink` / :func:`broadlink_to_lirc`
    round-trip on.

    Returns ``(timings, repeat_count)`` with even indices positive
    (marks) and odd indices negative (spaces) so the captured pulse
    feeds straight into ``PulsePayload.raw_timings``.
    """
    if len(packet) < 4:
        raise BroadlinkFormatError(
            f"IR packet too short: {len(packet)} bytes (need at least 4)"
        )
    repeat_count = packet[1]
    length = packet[2] | (packet[3] << 8)
    pulses = packet[4 : 4 + length]

    # ``broadlink_to_lirc`` unpacks the 0x00-escaped tick stream into
    # microsecond pulse widths; we just alternate the sign to match
    # the raw_timings convention.
    widths = broadlink_to_lirc(bytes(pulses))
    timings: list[int] = []
    for i, us in enumerate(widths):
        timings.append(abs(us) if i % 2 == 0 else -abs(us))
    return timings, repeat_count

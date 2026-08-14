"""Pulse-capture normalization — raw timings → tiered identity.

A :class:`NormalizedSignal` carries every identity tier we can compute
from a capture, plus the raw timings for storage. Pure: no I/O, no
HA imports.
"""
from __future__ import annotations

from dataclasses import dataclass

from custom_components.rune.domain.enums import SignalCategory, SignalTransport
from custom_components.rune.domain.identity.byte_hash import compute_byte_hash
from custom_components.rune.domain.identity.sl_pattern import (
    extract_device_address,
    extract_sl_pattern,
)


@dataclass(frozen=True)
class NormalizedSignal:
    """A capture fully normalized for downstream matching and storage."""

    transport: SignalTransport
    carrier_frequency_hz: int
    protocol_label: str | None
    code_hex: str | None
    raw_timings: tuple[int, ...]
    sl_fingerprint: str          # tier-3
    byte_hash: str | None        # tier-2
    decoded_fingerprint: str | None  # tier-1
    device_address: str | None


def normalize(
    *,
    timings: list[int] | tuple[int, ...],
    signal_category: SignalCategory,
    protocol_label: str | None = None,
    code_hex: str | None = None,
    decoded_fingerprint: str | None = None,
) -> NormalizedSignal:
    """Compute the three identity tiers for a capture.

    The caller decides what protocol was decoded (if any) and supplies
    the decoded fingerprint. The function computes the S/L fingerprint
    and byte hash from the raw timings, and the device address from
    the protocol + code.

    For unrecognized protocols, pass ``decoded_fingerprint=None``.
    For Pronto captures, also pass ``code_hex`` so ``extract_device_address``
    can pull the NEC address bytes when applicable.
    """
    timings_tuple = tuple(int(t) for t in timings)
    return NormalizedSignal(
        transport=signal_category.transport,
        carrier_frequency_hz=signal_category.carrier_frequency_hz,
        protocol_label=protocol_label,
        code_hex=code_hex,
        raw_timings=timings_tuple,
        sl_fingerprint=extract_sl_pattern(timings_tuple),
        byte_hash=compute_byte_hash(timings_tuple),
        decoded_fingerprint=decoded_fingerprint,
        device_address=extract_device_address(protocol_label, code_hex),
    )

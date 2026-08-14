"""Pronto S/L (short/long) fingerprint extraction.

A timing word magnitude below ``SL_THRESHOLD_US`` is "short" (``S``);
above is "long" (``L``). Two captures of the same button on the same
remote collapse to the same S/L string under normal receiver jitter.

Note: sub-threshold protocols (Sony SIRC, Panasonic/Kaseikyo, TCL) sit
near the threshold and can flip on jitter — that's why tier 2 (byte
hash) exists as a tiebreaker. This function is the tier-3 fallback.
"""
from __future__ import annotations

from custom_components.rune.const import GAP_THRESHOLD_US, SL_THRESHOLD_US


def extract_sl_pattern(timings: list[int]) -> str:
    """Return the S/L fingerprint of a timing array.

    Rules:

    - Magnitude ``>= GAP_THRESHOLD_US`` is an end-of-signal gap;
      it is appended as a single ``G`` then the function stops. (Gap
      handling matters for grouping captures of preambles that include
      the lead-in mark, which is large but not actually a gap.)
    - Magnitude ``>= SL_THRESHOLD_US`` is ``L``; otherwise ``S``.
    - Marks and spaces are interleaved in the output (a 9000/4500
      NEC preamble yields ``LL`` followed by the data payload).
    """
    parts: list[str] = []
    for value in timings:
        magnitude = abs(int(value))
        if magnitude >= GAP_THRESHOLD_US:
            parts.append("G")
            break
        parts.append("L" if magnitude >= SL_THRESHOLD_US else "S")
    return "".join(parts)


def extract_device_address(
    protocol_label: str | None,
    code_hex: str | None,
) -> str | None:
    """Best-effort device-address extraction for grouping.

    The only protocol that produces a stable, parsable address from the
    raw Pronto code today is NEC. Returns the address word formatted as
    ``"0xFB04"`` or ``None`` when it cannot be determined.

    In a Pronto-encoded NEC capture, the layout is:

        word 0..3   Pronto header (frequency, length1, length2, pad)
        word 4      NEC address (16-bit)
        word 5      NEC command (8-bit)
        word 6      NEC command complement (8-bit)
    """
    if not protocol_label or not code_hex:
        return None
    if protocol_label.upper() != "NEC":
        return None
    words = _parse_pronto_words(code_hex)
    if len(words) < 5:
        return None
    address = words[4]
    return f"0x{address:04X}"


def _parse_pronto_words(hex_str: str) -> list[int]:
    """Parse a Pronto hex string into timing words.

    Returns ``[]`` for malformed input rather than raising — this is a
    best-effort extractor used for grouping, not for storage.
    """
    cleaned = hex_str.replace(" ", "")
    if len(cleaned) % 4 != 0:
        return []
    try:
        return [int(cleaned[i : i + 4], 16) for i in range(0, len(cleaned), 4)]
    except ValueError:
        return []

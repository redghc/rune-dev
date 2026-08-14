"""Pronto hex ⇄ signed alternating microsecond raw timings.

The Pronto format is documented at https://www.remotecentral.com/features/irdb2.htm
but the relevant facts for RUNE are:

- Header is 4 words: frequency, length1 (sequence #1), length2 (sequence #2),
  then a sequence of timing words (pulse widths in Pronto units).
- A frequency word of ``0x0000`` means "raw timings, already in microseconds".
- Otherwise, 1 timing unit = ``0.241246`` microseconds (the Pronto spec's
  fixed-point carrier-cycle to microseconds conversion at 1 MHz).

For RUNE's purposes, the output of ``pronto_hex_to_raw_timings`` is exactly
the ``PulsePayload.raw_timings`` format: even indices positive (marks),
odd indices negative (spaces).
"""
from __future__ import annotations

# 1 timing unit = 0.241246 microseconds.
_PRONTO_FREQ_FACTOR = 0.241246
# A "learned / raw" Pronto code has frequency word zero.
_PRONTO_LEARNED_FREQ_WORD = 0x0000


class ProntoFormatError(ValueError):
    """Raised when a Pronto hex string is malformed."""


def _pronto_words(hex_str: str) -> list[int]:
    """Parse a Pronto hex string into 16-bit timing words.

    Accepts spaced (``"0000 0068 ..."``) or compact (``"00000068..."``)
    form. All ASCII whitespace (spaces, tabs, newlines, carriage
    returns) is stripped. Raises :class:`ProntoFormatError` on a bad
    number of digits or non-hex characters.
    """
    cleaned = "".join(hex_str.split())
    if len(cleaned) % 4 != 0:
        raise ProntoFormatError(
            f"Pronto hex must have a multiple of 4 hex digits (16-bit words); got {len(cleaned)}"
        )
    try:
        return [int(cleaned[i : i + 4], 16) for i in range(0, len(cleaned), 4)]
    except ValueError as err:
        raise ProntoFormatError(f"Non-hex character in Pronto code: {err}") from err


def pronto_hex_to_raw_timings(hex_str: str) -> list[int]:
    """Convert a Pronto hex code to signed alternating microsecond timings.

    A learned/raw Pronto code (frequency word ``0x0000``) is passed
    through as microseconds. A non-zero frequency word triggers the
    Pronto unit → microsecond conversion via ``_PRONTO_FREQ_FACTOR``.
    """
    words = _pronto_words(hex_str)
    if not words:
        raise ProntoFormatError("Pronto hex is empty")
    frequency_word = words[0]
    period_us_per_cycle = (
        1.0 if frequency_word == _PRONTO_LEARNED_FREQ_WORD else _PRONTO_FREQ_FACTOR
    )
    pulse_words = words[4:]  # skip 4-word header
    timings: list[int] = []
    for index, word in enumerate(pulse_words):
        microseconds = round(word * period_us_per_cycle)
        if index % 2 == 0:
            timings.append(abs(microseconds))
        else:
            timings.append(-abs(microseconds))
    return timings


def raw_timings_to_pronto_hex(
    timings: list[int],
    *,
    frequency_hz: int | None = None,
) -> str:
    """Convert signed alternating microsecond timings to a Pronto hex code.

    With ``frequency_hz=None`` (or ``<= 0``), emits a "learned/raw" header
    (``0x0000 ...``) so the timings are stored verbatim. Otherwise emits
    the proper frequency word and converts microseconds to carrier cycles.
    """
    if frequency_hz is None or frequency_hz <= 0:
        words: list[int] = [_PRONTO_LEARNED_FREQ_WORD, 0, 0, 0]
        body: list[int] = [abs(t) for t in timings]
    else:
        cycles_per_us = frequency_hz / 1_000_000.0
        freq_word = round(1.0 / (cycles_per_us * _PRONTO_FREQ_FACTOR))
        words = [freq_word, 0, 0, 0]
        body = [round(abs(t) * cycles_per_us) for t in timings]
    words.extend(body)
    return " ".join(f"{w:04X}" for w in words)

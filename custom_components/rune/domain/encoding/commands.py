"""Pure-Python command shims for HA's infrared / radio_frequency helpers.

HA's emitter platforms (Broadlink, ESPHome, …) only consume a small
attribute surface on the command object:

- IR emitters (Broadlink, ESPHome): ``command.get_raw_timings()`` and
  (ESPHome only) ``command.modulation``.
- RF emitters (Broadlink, ESPHome): ``command.frequency``,
  ``command.modulation``, ``command.repeat_count`` and
  ``command.get_raw_timings()``.

These helpers wrap raw timings and Pronto hex in objects that satisfy
those interfaces — without depending on the optional ``infrared_protocols``
and ``rf_protocols`` third-party libraries that HA core ships with but a
stripped-down install can miss.

Why not just ``from infrared_protocols.commands.raw import RawTimingCommand``
the way the rest of the HA ecosystem does? Two reasons:

1. **Robust install paths.** RUNE has to work on every HA host a user
   installs it on, including images that strip the optional IR/RF libs.
   Re-installing ``homeassistant`` is not a useful suggestion in that
   case (see the old error: "reinstall the homeassistant package …").
2. **Forward compatibility.** When the real lib IS available we still
   subclass its base (when importable) so any future
   ``isinstance(cmd, Command)`` check in HA core keeps working — but
   we skip ``super().__init__()`` because the constructor signatures
   drift between library releases (the same trick ``clevrdavid/rf_fan``
   uses for its ``CapturedCommand``).

The shim classes only set the attributes the emitters read, and provide
``get_raw_timings()`` returning signed alternating microseconds
(marks positive, spaces negative). That is exactly what RUNE already
stores in :attr:`PulsePayload.raw_timings` — no conversion needed.
"""
from __future__ import annotations

from typing import Any

from custom_components.rune.domain.encoding.pronto import pronto_hex_to_raw_timings

# ---------------------------------------------------------------------------
# Base-class resolution — best-effort subclassing of the real lib when
# available, so we inherit any future isinstance gates HA core might add.
# ---------------------------------------------------------------------------

try:
    from infrared_protocols.commands import Command as _RealIRCommand
except ImportError:  # pragma: no cover - depends on host install
    _RealIRCommand = None


try:
    from rf_protocols import RadioFrequencyCommand as _RealRFCommand
except ImportError:  # pragma: no cover - depends on host install
    _RealRFCommand = None


# ``ModulationType`` lives in ``rf_protocols``. We need a sentinel value
# for the OOK modulation (Broadlink and ESPHome RF both require it); fall
# back to the integer 0 if the lib is missing — the Broadlink emitter
# only inspects it for validation, not for protocol behaviour.
try:
    from rf_protocols import ModulationType as _RealModulationType
except ImportError:  # pragma: no cover - depends on host install
    _RealModulationType = None


class _IRCommandBase:
    """Minimal ``Command``-compatible base for IR commands.

    Mirrors the surface of :class:`infrared_protocols.commands.Command`
    (modulation, repeat_count, get_raw_timings) so emitters that do
    ``isinstance(cmd, Command)`` keep working when our subclass is used.
    """


class _RFCommandBase:
    """Minimal ``RadioFrequencyCommand``-compatible base for RF commands.

    Mirrors the surface of
    :class:`rf_protocols.RadioFrequencyCommand` (frequency, modulation,
    repeat_count, get_raw_timings) — same rationale as :class:`_IRCommandBase`.
    """


# Promote the real bases when available so isinstance checks against
# ``infrared_protocols.commands.Command`` / ``rf_protocols.RadioFrequencyCommand``
# succeed. The shim classes below inherit from whichever resolved.
_IR_BASE = _RealIRCommand if _RealIRCommand is not None else _IRCommandBase
_RF_BASE = _RealRFCommand if _RealRFCommand is not None else _RFCommandBase


class RawTimingIRCommand(_IR_BASE):
    """A raw-timing IR command, replayed through HA's ``infrared`` helper.

    Mirrors :class:`infrared_protocols.commands.raw.RawTimingCommand`
    (which has been in/out of the public surface across releases) using
    only the attributes HA's IR emitters actually read:

    - ``modulation`` — carrier frequency in Hz.
    - ``get_raw_timings()`` — signed alternating microsecond timings.

    We deliberately do NOT call ``super().__init__()`` so we stay immune
    to library-constructor drift across ``infrared_protocols`` versions.
    """

    def __init__(
        self,
        *,
        timings: list[int],
        modulation: int,
        repeat_count: int = 0,
    ) -> None:
        self.modulation = int(modulation)
        self.repeat_count = int(repeat_count)
        self._timings = [int(t) for t in timings]

    def get_raw_timings(self) -> list[int]:
        return self._timings


class ProntoIRCommand(_IR_BASE):
    """A Pronto-hex IR command, decoded to raw timings at construction.

    HA's IR emitters call ``get_raw_timings()`` and read ``modulation``.
    The Pronto format's only added value is convenience — we decode
    it once at construction using RUNE's own :func:`pronto_hex_to_raw_timings`
    (no library needed) and hand back the same signed alternating
    microsecond timings the raw-timing path uses.
    """

    def __init__(
        self,
        *,
        pronto_hex: str,
        modulation: int,
        repeat_count: int = 0,
    ) -> None:
        self.modulation = int(modulation)
        self.repeat_count = int(repeat_count)
        self._timings = pronto_hex_to_raw_timings(pronto_hex)

    def get_raw_timings(self) -> list[int]:
        return self._timings


class RawTimingRFCommand(_RF_BASE):
    """A raw-timing RF command, replayed through HA's ``radio_frequency``.

    Mirrors the surface of :class:`rf_protocols.RadioFrequencyCommand`
    that HA's RF emitters consume (ESPHome, Broadlink):

    - ``frequency`` — carrier frequency in Hz.
    - ``modulation`` — :class:`rf_protocols.ModulationType` value
      (we use ``ModulationType.OOK`` when the lib is importable,
      else ``0`` as a sentinel — the Broadlink encoder doesn't inspect it).
    - ``repeat_count`` — additional transmissions after the first.
    - ``get_raw_timings()`` — signed alternating microsecond timings.

    Same forward-compat trick as :class:`RawTimingIRCommand`: we skip
    ``super().__init__()`` so library-constructor drift across
    ``rf_protocols`` releases can't break us.
    """

    _OOK: Any = getattr(_RealModulationType, "OOK", 0)

    def __init__(
        self,
        *,
        frequency: int,
        timings: list[int],
        repeat_count: int = 0,
    ) -> None:
        self.frequency = int(frequency)
        self.modulation = self._OOK
        self.repeat_count = int(repeat_count)
        self._timings = [int(t) for t in timings]

    def get_raw_timings(self) -> list[int]:
        return self._timings


__all__ = [
    "ProntoIRCommand",
    "RawTimingIRCommand",
    "RawTimingRFCommand",
]

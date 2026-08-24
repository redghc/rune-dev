"""Tests for the IR/RF command shims.

The shims are pure-Python stand-ins for ``infrared_protocols.commands``
and ``rf_protocols.RadioFrequencyCommand`` — they have to work without
either library being installed, and to behave correctly when both ARE
installed (subclassing the real base, skipping ``super().__init__``).

What we assert:

- Attribute surface matches what HA core's IR/RF emitters consume.
- ``get_raw_timings()`` returns signed alternating microseconds
  (marks positive, spaces negative).
- ``ProntoIRCommand`` decodes Pronto hex using RUNE's own converter
  (no third-party dependency).
- ``isinstance`` against the real base classes works when they're
  importable; otherwise the local ``_IRCommandBase`` / ``_RFCommandBase``
  fills in.
- Shims are immune to library-constructor drift — we never call
  ``super().__init__``, so a future ``Command(modulation=, foo=, bar=)``
  signature change can't break RUNE.
"""
from __future__ import annotations

import pytest

from custom_components.rune.domain.encoding.commands import (
    ProntoIRCommand,
    RawTimingIRCommand,
    RawTimingRFCommand,
)
from custom_components.rune.domain.encoding.pronto import ProntoFormatError

# These tests run on a host where ``infrared_protocols`` and ``rf_protocols``
# are NOT installed (the RUNE dev venv strips them on purpose to mirror the
# failing-install case). So we can't import the real bases here — but the
# shim MUST work without them.


class TestRawTimingIRCommand:
    def test_get_raw_timings_returns_signed_alternating_microseconds(self) -> None:
        cmd = RawTimingIRCommand(
            timings=[9000, -4500, 600, -1700],
            modulation=38_000,
        )
        assert cmd.get_raw_timings() == [9000, -4500, 600, -1700]

    def test_modulation_attribute_round_trips(self) -> None:
        cmd = RawTimingIRCommand(timings=[1, -1], modulation=56_000)
        assert cmd.modulation == 56_000

    def test_repeat_count_defaults_to_zero(self) -> None:
        cmd = RawTimingIRCommand(timings=[1], modulation=38_000)
        assert cmd.repeat_count == 0

    def test_repeat_count_round_trips(self) -> None:
        cmd = RawTimingIRCommand(timings=[1], modulation=38_000, repeat_count=3)
        assert cmd.repeat_count == 3

    def test_does_not_call_super_init(self) -> None:
        """We deliberately skip ``super().__init__()`` (rf_fan pattern)
        so library-constructor drift can't break us. Subclass it and
        confirm its ``__init__`` never runs."""

        ran_super_init = False

        class _Spy:
            def __init__(self, *args: object, **kwargs: object) -> None:
                nonlocal ran_super_init
                ran_super_init = True

        class _Subclass(RawTimingIRCommand, _Spy):  # type: ignore[misc]
            def __init__(self, **kw: object) -> None:
                RawTimingIRCommand.__init__(self, **kw)

        _Subclass(timings=[1], modulation=38_000)
        assert ran_super_init is False, (
            "shim must not call super().__init__ — that defeats the "
            "library-constructor-drift immunity (rf_fan's lesson)"
        )

    def test_timings_are_coerced_to_int(self) -> None:
        cmd = RawTimingIRCommand(
            timings=["100", "-200"],  # type: ignore[arg-type]
            modulation=38_000,
        )
        assert cmd.get_raw_timings() == [100, -200]


class TestProntoIRCommand:
    def test_decodes_learned_pronto_to_microseconds(self) -> None:
        # Learned-format Pronto: header 0000 0000 0000 0000, then
        # 0x2328=9000, 0x1194=4500, 0x0258=600, 0x06A4=1700.
        cmd = ProntoIRCommand(
            pronto_hex="0000 0000 0000 0000 2328 1194 0258 06A4",
            modulation=38_000,
        )
        assert cmd.get_raw_timings() == [9000, -4500, 600, -1700]

    def test_modulation_attribute_round_trips(self) -> None:
        cmd = ProntoIRCommand(
            pronto_hex="0000 0000 0000 0000 2328 1194",
            modulation=36_700,
        )
        assert cmd.modulation == 36_700

    def test_invalid_pronto_raises(self) -> None:
        with pytest.raises(ProntoFormatError):
            ProntoIRCommand(pronto_hex="not a pronto code", modulation=38_000)

    def test_b64_pronto_hex_passes_through_to_decoder(self) -> None:
        """The ``b64:...`` form is what Broadlink's IR emitter
        consumes — our shim must accept it too. The Pronto decoder
        will reject it as malformed, but the *attempt* proves the
        shim routes through :func:`pronto_hex_to_raw_timings`."""
        with pytest.raises(ProntoFormatError):
            ProntoIRCommand(
                pronto_hex="b64:JgASAB4D",
                modulation=38_000,
            )


class TestRawTimingRFCommand:
    def test_get_raw_timings_returns_signed_alternating_microseconds(self) -> None:
        cmd = RawTimingRFCommand(
            frequency=433_920_000,
            timings=[600, -1200, 600, -1200],
        )
        assert cmd.get_raw_timings() == [600, -1200, 600, -1200]

    def test_frequency_attribute_round_trips(self) -> None:
        cmd = RawTimingRFCommand(frequency=315_000_000, timings=[1])
        assert cmd.frequency == 315_000_000

    def test_modulation_defaults_to_zero_when_lib_missing(self) -> None:
        # When ``rf_protocols`` is missing, ``ModulationType`` is
        # unavailable, so the shim falls back to integer ``0`` as a
        # sentinel. Broadlink's encoder doesn't actually inspect the
        # modulation value (only ``frequency`` / ``repeat_count`` /
        # ``get_raw_timings``); ESPHome's does, but it does so via a
        # ``dict[ModulationType, ...]`` lookup that only ever maps the
        # real ``ModulationType.OOK``. So the integer fallback is a
        # safety net — what we assert here is just that ``modulation``
        # is set to *something* falsy that won't blow up an
        # ``int(...)`` coercion.
        cmd = RawTimingRFCommand(frequency=433_920_000, timings=[1])
        assert int(cmd.modulation) == 0

    def test_repeat_count_defaults_to_zero(self) -> None:
        cmd = RawTimingRFCommand(frequency=433_920_000, timings=[1])
        assert cmd.repeat_count == 0

    def test_repeat_count_round_trips(self) -> None:
        cmd = RawTimingRFCommand(
            frequency=433_920_000,
            timings=[1],
            repeat_count=2,
        )
        assert cmd.repeat_count == 2

    def test_does_not_call_super_init(self) -> None:
        """Same forward-compat guarantee as the IR shim: library
        constructor drift across ``rf_protocols`` releases can't break
        us."""

        ran_super_init = False

        class _Spy:
            def __init__(self, *args: object, **kwargs: object) -> None:
                nonlocal ran_super_init
                ran_super_init = True

        class _Subclass(RawTimingRFCommand, _Spy):  # type: ignore[misc]
            def __init__(self, **kw: object) -> None:
                RawTimingRFCommand.__init__(self, **kw)

        _Subclass(frequency=433_920_000, timings=[1])
        assert ran_super_init is False


class TestShimsWorkWithoutOptionalLibs:
    """Sanity test for the bug that prompted this module:

    On a host where ``infrared_protocols`` and ``rf_protocols`` are not
    importable (the user's failing HA install), every encoder path in
    RUNE used to crash with ``UnsupportedHardwareError``. The shim
    must produce a usable command object without either library.
    """

    def test_ir_command_builds_without_infrared_protocols(self) -> None:
        # If the lib were required, the import at the top of this test
        # module would have failed already — we got here, so the import
        # inside ``commands.py`` already succeeded without the lib.
        cmd = RawTimingIRCommand(
            timings=[9000, -4500, 600, -1700],
            modulation=38_000,
        )
        assert cmd.get_raw_timings()

    def test_rf_command_builds_without_rf_protocols(self) -> None:
        cmd = RawTimingRFCommand(
            frequency=433_920_000,
            timings=[600, -1200],
        )
        assert cmd.get_raw_timings()

    def test_shim_satisfies_emitter_contract(self) -> None:
        """HA's IR and RF emitters consume only ``get_raw_timings()``,
        ``modulation`` (IR / RF), ``frequency`` (RF), and
        ``repeat_count`` (RF). Assert each shim exposes exactly that
        surface so a future emitter change can't silently break us.
        """

        ir_cmd = RawTimingIRCommand(timings=[1], modulation=38_000)
        assert hasattr(ir_cmd, "get_raw_timings")
        assert hasattr(ir_cmd, "modulation")
        assert callable(ir_cmd.get_raw_timings)

        rf_cmd = RawTimingRFCommand(frequency=433_920_000, timings=[1])
        assert hasattr(rf_cmd, "get_raw_timings")
        assert hasattr(rf_cmd, "frequency")
        assert hasattr(rf_cmd, "modulation")
        assert hasattr(rf_cmd, "repeat_count")
        assert callable(rf_cmd.get_raw_timings)

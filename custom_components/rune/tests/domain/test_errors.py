"""Tests for the typed error hierarchy."""
from __future__ import annotations

from custom_components.rune.domain.errors import (
    ActionError,
    ActionTargetNotFoundError,
    CaptureAbortedError,
    CaptureError,
    CaptureProviderUnavailableError,
    CaptureTimeoutError,
    CommandNotLearnedError,
    ConfigError,
    InvalidProfileError,
    MigrationError,
    NoReceiverError,
    NoTransmitterError,
    RuneError,
    StorageError,
    TransmitError,
    TxGateTimeoutError,
    UnsupportedHardwareError,
    UnsupportedProtocolError,
    ValidationError,
)


class TestHierarchy:
    def test_all_inherit_from_rune_error(self) -> None:
        for cls in (
            ConfigError,
            NoTransmitterError,
            NoReceiverError,
            InvalidProfileError,
            CaptureError,
            CaptureTimeoutError,
            CaptureAbortedError,
            CaptureProviderUnavailableError,
            UnsupportedProtocolError,
            TransmitError,
            UnsupportedHardwareError,
            TxGateTimeoutError,
            CommandNotLearnedError,
            StorageError,
            MigrationError,
            ValidationError,
            ActionError,
            ActionTargetNotFoundError,
        ):
            assert issubclass(cls, RuneError), cls

    def test_subcategory_grouping(self) -> None:
        # Config children
        assert issubclass(NoTransmitterError, ConfigError)
        # Capture children
        assert issubclass(CaptureTimeoutError, CaptureError)
        # Transmit children
        assert issubclass(CommandNotLearnedError, TransmitError)
        # Storage children
        assert issubclass(MigrationError, StorageError)
        # Action children
        assert issubclass(ActionTargetNotFoundError, ActionError)


class TestRaising:
    def test_can_catch_via_base(self) -> None:
        with __import__("pytest").raises(RuneError):
            raise CaptureTimeoutError("nothing arrived in 30s")

    def test_can_catch_via_mid_category(self) -> None:
        with __import__("pytest").raises(CaptureError):
            raise CaptureTimeoutError("nothing arrived in 30s")

    def test_error_message_preserved(self) -> None:
        err = NoTransmitterError("no RF transmitter configured")
        assert str(err) == "no RF transmitter configured"

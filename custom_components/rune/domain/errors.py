"""Typed error hierarchy for RUNE.

Domain code raises these errors. Adapters translate them into
``HomeAssistantError`` (or leave them) at the boundary. Bare
``Exception`` is forbidden; ``noqa: BLE001`` is forbidden.
"""
from __future__ import annotations


class RuneError(Exception):
    """Base class for every RUNE-raised error.

    All other errors in this module subclass ``RuneError``. Callers
    that want to catch *any* RUNE failure should catch this.
    """


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------

class ConfigError(RuneError):
    """Configuration is invalid or incomplete."""


class NoTransmitterError(ConfigError):
    """No transmitter is available for the requested transport."""


class NoReceiverError(ConfigError):
    """No receiver is available to capture a signal."""


class InvalidProfileError(ConfigError):
    """A DeviceProfile failed validation."""


# ---------------------------------------------------------------------------
# Capture errors
# ---------------------------------------------------------------------------

class CaptureError(RuneError):
    """A capture session failed in some way."""


class CaptureTimeoutError(CaptureError):
    """The learn/capture window elapsed without a signal arriving."""


class CaptureAbortedError(CaptureError):
    """The capture was cancelled by user request."""


class CaptureProviderUnavailableError(CaptureError):
    """The chosen capture provider is not available right now."""


class UnsupportedProtocolError(CaptureError):
    """The captured signal could not be decoded by any known protocol."""


# ---------------------------------------------------------------------------
# Transmit errors
# ---------------------------------------------------------------------------

class TransmitError(RuneError):
    """A transmit call failed in some way."""


class UnsupportedHardwareError(TransmitError):
    """The selected transmitter cannot send this kind of command."""


class TxGateTimeoutError(TransmitError):
    """The TX gate could not schedule the send within the wait window."""


class CommandNotLearnedError(TransmitError):
    """The requested command_key has no learned pulse."""


# ---------------------------------------------------------------------------
# Storage / migration errors
# ---------------------------------------------------------------------------

class StorageError(RuneError):
    """Persistence or migration failed."""


class MigrationError(StorageError):
    """A schema migration could not be applied."""


class ValidationError(StorageError):
    """A loaded record failed schema validation."""


# ---------------------------------------------------------------------------
# Trigger / action errors
# ---------------------------------------------------------------------------

class ActionError(RuneError):
    """A triggered action could not execute."""


class ActionTargetNotFoundError(ActionError):
    """The action's target entity/service no longer exists."""

"""Enumerations for RUNE's domain taxonomy.

These enums are the canonical vocabulary for entity types, signal
carriers, command semantics, speed models, and action targets. They are
referenced by both the pure domain layer and the HA platform adapters.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from custom_components.rune.const import DEFAULT_IR_CARRIER_HZ

# ---------------------------------------------------------------------------
# EntityCategory — what the user-facing entity *is*
# ---------------------------------------------------------------------------

class EntityCategory(StrEnum):
    """High-level shape of a user-facing HA entity."""

    FAN = "fan"
    CLIMATE = "climate"
    LIGHT = "light"
    COVER = "cover"
    MEDIA_PLAYER = "media_player"
    SWITCH = "switch"
    REMOTE = "remote"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Signal transport + encoding
# ---------------------------------------------------------------------------

class SignalTransport(StrEnum):
    """Physical carrier family."""

    RF = "rf"
    IR = "ir"


class SignalEncoding(StrEnum):
    """How the pulse train is represented in storage."""

    RAW_TIMINGS = "raw_timings"
    DECODED = "decoded"
    BASE64_PACKET = "base64_packet"
    JSON_PAYLOAD = "json_payload"


@dataclass(frozen=True)
class SignalCategory:
    """The carrier + encoding combo a signal rides on."""

    transport: SignalTransport
    encoding: SignalEncoding
    carrier_frequency_hz: int

    def __post_init__(self) -> None:
        if self.carrier_frequency_hz <= 0:
            raise ValueError(
                f"carrier_frequency_hz must be positive, got {self.carrier_frequency_hz}"
            )

    @classmethod
    def default_ir(cls) -> SignalCategory:
        return cls(
            transport=SignalTransport.IR,
            encoding=SignalEncoding.RAW_TIMINGS,
            carrier_frequency_hz=DEFAULT_IR_CARRIER_HZ,
        )

    @classmethod
    def default_rf(cls, frequency_hz: int) -> SignalCategory:
        return cls(
            transport=SignalTransport.RF,
            encoding=SignalEncoding.RAW_TIMINGS,
            carrier_frequency_hz=frequency_hz,
        )

    def with_encoding(self, encoding: SignalEncoding) -> SignalCategory:
        return SignalCategory(
            transport=self.transport,
            encoding=encoding,
            carrier_frequency_hz=self.carrier_frequency_hz,
        )


# ---------------------------------------------------------------------------
# CommandCategory — semantic of a learned pulse
# ---------------------------------------------------------------------------

class CommandCategory(StrEnum):
    """What a learned pulse means to the user/device."""

    POWER = "power"
    TRANSPORT = "transport"          # play/pause/stop/next/prev
    VOLUME = "volume"
    CHANNEL = "channel"
    NAVIGATION = "navigation"        # up/down/left/right/ok
    MODE = "mode"                    # hvac mode / source / fan mode
    TEMPERATURE = "temperature"
    FAN_SPEED = "fan_speed"
    BRIGHTNESS = "brightness"
    COLOR_TEMP = "color_temp"
    COVER = "cover"                  # open/close/stop
    SPEED_PRESET = "speed_preset"    # discrete speed_N
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# SpeedMode — fan entity speed model
# ---------------------------------------------------------------------------

class SpeedMode(StrEnum):
    """How a fan entity exposes its speeds to HA."""

    PERCENTAGE = "percentage"   # 0..100 only, mapped to N steps
    DISCRETE = "discrete"       # 1..N only, no percentage exposed
    HYBRID = "hybrid"           # both percentage and discrete


# ---------------------------------------------------------------------------
# ActionKind — what an action binding does when triggered
# ---------------------------------------------------------------------------

class ActionKind(StrEnum):
    """Target kind for an action binding."""

    PRESS_BUTTON = "press_button"
    CALL_SERVICE = "call_service"
    ACTIVATE_SCENE = "activate_scene"
    RUN_SCRIPT = "run_script"
    FIRE_EVENT = "fire_event"


# ---------------------------------------------------------------------------
# CaptureState — state of an in-flight capture session
# ---------------------------------------------------------------------------

class CaptureState(StrEnum):
    """Capture session lifecycle states."""

    IDLE = "idle"
    LISTENING = "listening"
    CAPTURED = "captured"
    TIMEOUT = "timeout"
    ERROR = "error"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Receiver source kind — how a receiver reports signals
# ---------------------------------------------------------------------------

class ReceiverSourceKind(StrEnum):
    """How a receiver entity delivers signals to RUNE."""

    NATIVE_INFRARED = "native_infrared"   # HA 2026.6+ InfraredReceiverEntity
    BROADLINK_RF = "broadlink_rf"        # Broadlink sweep+capture flow
    ESPHOME_LEGACY_IR = "esphome_legacy_ir"  # esphome.remote_received event bus
    MOCK = "mock"                          # test fixture


# ---------------------------------------------------------------------------
# Transmitter source kind
# ---------------------------------------------------------------------------

class TransmitterSourceKind(StrEnum):
    """How a transmitter entity accepts commands from RUNE."""

    NATIVE_INFRARED = "native_infrared"
    NATIVE_RADIO_FREQUENCY = "native_radio_frequency"
    BROADLINK_INFRARED = "broadlink_infrared"
    BROADLINK_RADIO_FREQUENCY = "broadlink_radio_frequency"
    ESPHOME_INFRARED = "esphome_infrared"
    ESPHOME_RADIO_FREQUENCY = "esphome_radio_frequency"
    MOCK = "mock"

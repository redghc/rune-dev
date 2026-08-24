"""Data models for RUNE.

Pure Python dataclasses with explicit ``to_dict`` / ``from_dict`` for
persistence. Value objects (immutable identity) are ``frozen=True``;
aggregates (mutable device state) are not.

Design rules:

- No method touches the network or filesystem.
- No method imports from ``homeassistant.*``.
- ``from_dict`` is **strict about required fields**: missing required
  fields raise ``ValidationError`` with a clear message rather than
  silently defaulting to wrong values.
- ``from_dict`` is **lenient about legacy optional fields**: missing
  optional fields fall back to documented defaults.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from .enums import (
    ActionKind,
    CommandCategory,
    EntityCategory,
    SignalCategory,
    SpeedMode,
)
from .errors import ValidationError
from .time import utcnow_iso

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require(mapping: dict[str, Any], key: str) -> Any:
    """Return ``mapping[key]`` or raise ``ValidationError``."""
    if key not in mapping:
        raise ValidationError(f"Missing required field: {key!r}")
    return mapping[key]


def _optional_str(value: Any) -> str | None:
    """Coerce to str-or-None. Empty strings become None."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"Expected str, got {type(value).__name__}")
    return value or None


def new_id() -> str:
    """Generate a fresh UUID4 string for any model id field.

    Public re-export of the internal id factory for use outside
    ``models.py`` (adapters that need to mint ``UnknownSignal`` /
    ``ActionBinding`` rows on the fly, the sniffer engine, etc.).
    """
    return str(uuid4())


# ---------------------------------------------------------------------------
# PulsePayload — discriminated union of supported command encodings
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PulsePayload:
    """The wire-format payload of a learned pulse command.

    Exactly ONE of ``raw_timings``, ``decoded_hex``, ``base64_packet``,
    or ``json_payload`` should be populated for a given command, though
    the model permits multiple to coexist for the same command (e.g.
    a decoded identity with a captured fallback Pronto).

    ``repeat_count`` is the per-protocol ditto count (NEC: same frame
    repeated ``repeat_count + 1`` times). ``send_count`` is the
    whole-frame loop count — orthogonal to ``repeat_count``.
    """

    raw_timings: tuple[int, ...] | None = None
    decoded_hex: str | None = None
    base64_packet: str | None = None
    json_payload: dict[str, Any] | None = None
    repeat_count: int = 1
    send_count: int = 1

    def __post_init__(self) -> None:
        if self.repeat_count < 0:
            raise ValueError(f"repeat_count must be >= 0, got {self.repeat_count}")
        if self.send_count < 1:
            raise ValueError(f"send_count must be >= 1, got {self.send_count}")

    @property
    def is_empty(self) -> bool:
        """True when no payload field is populated.

        An empty tuple ``()`` counts as empty too — otherwise a
        command with ``raw_timings=()`` would pass the empty check,
        dispatch an empty pulse train, and silently no-op at the
        hardware (the user sees "Sent" but the device doesn't react).
        Same logic for empty strings / empty dicts on the other
        payload fields.
        """
        return all(
            not value
            for value in (self.raw_timings, self.decoded_hex, self.base64_packet, self.json_payload)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_timings": list(self.raw_timings) if self.raw_timings else None,
            "decoded_hex": self.decoded_hex,
            "base64_packet": self.base64_packet,
            "json_payload": dict(self.json_payload) if self.json_payload else None,
            "repeat_count": self.repeat_count,
            "send_count": self.send_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PulsePayload:
        raw = data.get("raw_timings")
        timings: tuple[int, ...] | None = None
        if raw is not None:
            if not isinstance(raw, list):
                raise ValidationError("raw_timings must be a list")
            timings = tuple(int(t) for t in raw)
        json_payload = data.get("json_payload")
        if json_payload is not None and not isinstance(json_payload, dict):
            raise ValidationError("json_payload must be a dict")
        return cls(
            raw_timings=timings,
            decoded_hex=_optional_str(data.get("decoded_hex")),
            base64_packet=_optional_str(data.get("base64_packet")),
            json_payload=dict(json_payload) if json_payload else None,
            repeat_count=int(data.get("repeat_count", 1)),
            send_count=int(data.get("send_count", 1)),
        )


# ---------------------------------------------------------------------------
# PulseCommand — a single learned pulse on a device
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PulseCommand:
    """A learned pulse bound to a device, addressable by ``key``."""

    key: str
    label: str
    category: CommandCategory
    signal_category: SignalCategory
    payload: PulsePayload

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "category": str(self.category),
            "signal_category": {
                "transport": str(self.signal_category.transport),
                "encoding": str(self.signal_category.encoding),
                "carrier_frequency_hz": self.signal_category.carrier_frequency_hz,
            },
            "payload": self.payload.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PulseCommand:
        key = data.get("key")
        if not key:
            raise ValidationError("PulseCommand.key is required")
        label = data.get("label")
        if label is None:
            label = key
        category = CommandCategory(data.get("category", CommandCategory.CUSTOM))
        signal = data.get("signal_category") or {}
        signal_category = SignalCategory(
            transport=signal.get("transport", "ir"),
            encoding=signal.get("encoding", "raw_timings"),
            carrier_frequency_hz=int(signal.get("carrier_frequency_hz", 0)) or 38_000,
        )
        payload = PulsePayload.from_dict(data.get("payload") or {})
        return cls(
            key=key,
            label=label,
            category=category,
            signal_category=signal_category,
            payload=payload,
        )


# ---------------------------------------------------------------------------
# ActionTarget — what to *do* when a trigger fires
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ActionTarget:
    """The payload an action binding invokes when fired."""

    kind: ActionKind
    # PRESS_BUTTON: (device_id, command_key)
    device_id: str | None = None
    command_key: str | None = None
    # CALL_SERVICE: (domain, service)
    service_domain: str | None = None
    service_name: str | None = None
    service_data: dict[str, Any] | None = None
    # ACTIVATE_SCENE / RUN_SCRIPT: entity_id
    target_entity_id: str | None = None
    # FIRE_EVENT: (event_type, data)
    event_type: str | None = None
    event_data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": str(self.kind),
            "device_id": self.device_id,
            "command_key": self.command_key,
            "service_domain": self.service_domain,
            "service_name": self.service_name,
            "service_data": dict(self.service_data) if self.service_data else None,
            "target_entity_id": self.target_entity_id,
            "event_type": self.event_type,
            "event_data": dict(self.event_data) if self.event_data else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionTarget:
        kind = ActionKind(_require(data, "kind"))
        service_data = data.get("service_data")
        if service_data is not None and not isinstance(service_data, dict):
            raise ValidationError("service_data must be a dict")
        event_data = data.get("event_data")
        if event_data is not None and not isinstance(event_data, dict):
            raise ValidationError("event_data must be a dict")
        return cls(
            kind=kind,
            device_id=_optional_str(data.get("device_id")),
            command_key=_optional_str(data.get("command_key")),
            service_domain=_optional_str(data.get("service_domain")),
            service_name=_optional_str(data.get("service_name")),
            service_data=dict(service_data) if service_data else None,
            target_entity_id=_optional_str(data.get("target_entity_id")),
            event_type=_optional_str(data.get("event_type")),
            event_data=dict(event_data) if event_data else None,
        )


# ---------------------------------------------------------------------------
# ActionBinding — a trigger (signal) → action (target) mapping
# ---------------------------------------------------------------------------

@dataclass
class ActionBinding:
    """A mapping from an arriving signal to an action invocation.

    ``signal_id`` may reference either a known ``PulseCommand`` or an
    ``UnknownSignal``. ``receiver_entity_ids`` empty = unscoped (fires
    for any receiver). ``min_hits`` presses must land within
    ``TRIGGER_HIT_RESET_WINDOW_S`` of the first press for the trigger
    to fire.
    """

    id: str
    name: str
    signal_id: str
    target: ActionTarget
    min_hits: int = 1
    receiver_entity_ids: list[str] = field(default_factory=list)
    enabled: bool = True
    created_at: str = field(default_factory=utcnow_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "signal_id": self.signal_id,
            "target": self.target.to_dict(),
            "min_hits": self.min_hits,
            "receiver_entity_ids": list(self.receiver_entity_ids),
            "enabled": self.enabled,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionBinding:
        receiver_ids = data.get("receiver_entity_ids") or []
        if not isinstance(receiver_ids, list):
            raise ValidationError("receiver_entity_ids must be a list")
        return cls(
            id=_require(data, "id"),
            name=data.get("name", ""),
            signal_id=_require(data, "signal_id"),
            target=ActionTarget.from_dict(_require(data, "target")),
            min_hits=max(1, int(data.get("min_hits", 1))),
            receiver_entity_ids=[str(r) for r in receiver_ids],
            enabled=bool(data.get("enabled", True)),
            created_at=data.get("created_at") or utcnow_iso(),
        )


# ---------------------------------------------------------------------------
# RuneDevice — top-level aggregate
# ---------------------------------------------------------------------------

@dataclass
class RuneDevice:
    """A RUNE-managed device: the parent aggregate that owns commands,
    sub-entity descriptors, power-monitor wiring, and action bindings.
    """

    id: str
    name: str
    category: EntityCategory
    manufacturer: str | None = None
    model: str | None = None
    transmitter_entity_ids: list[str] = field(default_factory=list)
    receiver_entity_ids: list[str] = field(default_factory=list)
    speed_mode: SpeedMode = SpeedMode.HYBRID
    discrete_speed_count: int = 3
    power_sensor_entity_id: str | None = None
    power_off_below_w: float | None = None
    power_on_above_w: float | None = None
    temperature_sensor_entity_id: str | None = None
    humidity_sensor_entity_id: str | None = None
    climate_matrix: bool = False
    commands: dict[str, PulseCommand] = field(default_factory=dict)
    actions: dict[str, ActionBinding] = field(default_factory=dict)
    version: int = 1
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)

    def __post_init__(self) -> None:
        if self.discrete_speed_count < 1:
            raise ValueError(
                f"discrete_speed_count must be >= 1, got {self.discrete_speed_count}"
            )

    # ------------------------------------------------------------------
    # Command helpers
    # ------------------------------------------------------------------

    def get_command(self, key: str) -> PulseCommand | None:
        """Return the command at ``key`` or ``None``."""
        return self.commands.get(key)

    def add_command(self, command: PulseCommand) -> None:
        """Add or replace a command. Bumps ``updated_at``."""
        self.commands[command.key] = command
        self.updated_at = utcnow_iso()

    def remove_command(self, key: str) -> bool:
        """Remove the command at ``key``. Returns True if removed."""
        if key not in self.commands:
            return False
        del self.commands[key]
        self.updated_at = utcnow_iso()
        return True

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": str(self.category),
            "manufacturer": self.manufacturer,
            "model": self.model,
            "transmitter_entity_ids": list(self.transmitter_entity_ids),
            "receiver_entity_ids": list(self.receiver_entity_ids),
            "speed_mode": str(self.speed_mode),
            "discrete_speed_count": self.discrete_speed_count,
            "power_sensor_entity_id": self.power_sensor_entity_id,
            "power_off_below_w": self.power_off_below_w,
            "power_on_above_w": self.power_on_above_w,
            "temperature_sensor_entity_id": self.temperature_sensor_entity_id,
            "humidity_sensor_entity_id": self.humidity_sensor_entity_id,
            "climate_matrix": self.climate_matrix,
            "commands": {k: c.to_dict() for k, c in self.commands.items()},
            "actions": {k: a.to_dict() for k, a in self.actions.items()},
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuneDevice:
        commands_data = data.get("commands")
        if commands_data is None:
            commands_data = {}
        if not isinstance(commands_data, dict):
            raise ValidationError("commands must be a dict of key → PulseCommand")
        actions_data = data.get("actions")
        if actions_data is None:
            actions_data = {}
        if not isinstance(actions_data, dict):
            raise ValidationError("actions must be a dict of key → ActionBinding")
        return cls(
            id=_require(data, "id"),
            name=data.get("name", ""),
            category=EntityCategory(data.get("category", EntityCategory.CUSTOM)),
            manufacturer=_optional_str(data.get("manufacturer")),
            model=_optional_str(data.get("model")),
            transmitter_entity_ids=[str(t) for t in (data.get("transmitter_entity_ids") or [])],
            receiver_entity_ids=[str(r) for r in (data.get("receiver_entity_ids") or [])],
            speed_mode=SpeedMode(data.get("speed_mode", SpeedMode.HYBRID)),
            discrete_speed_count=max(1, int(data.get("discrete_speed_count", 3))),
            power_sensor_entity_id=_optional_str(data.get("power_sensor_entity_id")),
            power_off_below_w=(
                float(data["power_off_below_w"])
                if data.get("power_off_below_w") is not None
                else None
            ),
            power_on_above_w=(
                float(data["power_on_above_w"])
                if data.get("power_on_above_w") is not None
                else None
            ),
            temperature_sensor_entity_id=_optional_str(data.get("temperature_sensor_entity_id")),
            humidity_sensor_entity_id=_optional_str(data.get("humidity_sensor_entity_id")),
            climate_matrix=bool(data.get("climate_matrix", False)),
            commands={k: PulseCommand.from_dict(v) for k, v in commands_data.items()},
            actions={k: ActionBinding.from_dict(v) for k, v in actions_data.items()},
            version=int(data.get("version", 1)),
            created_at=data.get("created_at") or utcnow_iso(),
            updated_at=data.get("updated_at") or utcnow_iso(),
        )


# ---------------------------------------------------------------------------
# UnknownSignal — a single unassigned captured signal
# ---------------------------------------------------------------------------

@dataclass
class UnknownSignal:
    """A single captured signal not yet assigned to a device."""

    id: str
    fingerprint: str                     # tier-3 S/L identity
    signal_category: SignalCategory
    raw_timings: tuple[int, ...]
    first_seen: str
    last_seen: str
    hit_count: int
    byte_hash: str | None = None         # tier-2 byte-quantized identity
    decoded_fingerprint: str | None = None  # tier-1 decoded-protocol identity
    protocol_label: str | None = None
    code_hex: str | None = None
    alias: str = ""
    source: Literal["sniffed", "manual", "imported"] = "sniffed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "fingerprint": self.fingerprint,
            "byte_hash": self.byte_hash,
            "decoded_fingerprint": self.decoded_fingerprint,
            "signal_category": {
                "transport": str(self.signal_category.transport),
                "encoding": str(self.signal_category.encoding),
                "carrier_frequency_hz": self.signal_category.carrier_frequency_hz,
            },
            "protocol_label": self.protocol_label,
            "code_hex": self.code_hex,
            "raw_timings": list(self.raw_timings),
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "hit_count": self.hit_count,
            "alias": self.alias,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnknownSignal:
        timings_data = data.get("raw_timings") or []
        if not isinstance(timings_data, list):
            raise ValidationError("raw_timings must be a list")
        signal = data.get("signal_category") or {}
        signal_category = SignalCategory(
            transport=signal.get("transport", "ir"),
            encoding=signal.get("encoding", "raw_timings"),
            carrier_frequency_hz=int(signal.get("carrier_frequency_hz", 0)) or 38_000,
        )
        return cls(
            id=_require(data, "id"),
            fingerprint=data.get("fingerprint", ""),
            byte_hash=_optional_str(data.get("byte_hash")),
            decoded_fingerprint=_optional_str(data.get("decoded_fingerprint")),
            signal_category=signal_category,
            protocol_label=_optional_str(data.get("protocol_label")),
            code_hex=_optional_str(data.get("code_hex")),
            raw_timings=tuple(int(t) for t in timings_data),
            first_seen=data.get("first_seen") or utcnow_iso(),
            last_seen=data.get("last_seen") or utcnow_iso(),
            hit_count=int(data.get("hit_count", 0)),
            alias=data.get("alias", "") or "",
            source=data.get("source", "sniffed"),
        )


# ---------------------------------------------------------------------------
# UnknownRemote — a group of unknown signals sharing a physical source
# ---------------------------------------------------------------------------

@dataclass
class UnknownRemote:
    """A group of unknown signals that appear to come from one remote."""

    id: str
    label: str | None
    protocol_label: str | None
    device_address: str | None
    signals: list[UnknownSignal] = field(default_factory=list)
    dismissed: bool = False
    first_seen: str = field(default_factory=utcnow_iso)
    last_seen: str = field(default_factory=utcnow_iso)
    hit_count: int = 0
    source: Literal["sniffed", "manual", "imported"] = "sniffed"

    def get_signal_by_id(self, signal_id: str) -> UnknownSignal | None:
        """Find a signal on this remote by its stable id."""
        for signal in self.signals:
            if signal.id == signal_id:
                return signal
        return None

    def remove_signal(self, signal_id: str) -> bool:
        """Remove a signal by id. Returns True if removed."""
        for index, signal in enumerate(self.signals):
            if signal.id == signal_id:
                del self.signals[index]
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "protocol_label": self.protocol_label,
            "device_address": self.device_address,
            "signals": [s.to_dict() for s in self.signals],
            "dismissed": self.dismissed,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "hit_count": self.hit_count,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnknownRemote:
        signals_data = data.get("signals") or []
        if not isinstance(signals_data, list):
            raise ValidationError("signals must be a list")
        return cls(
            id=_require(data, "id"),
            label=_optional_str(data.get("label")),
            protocol_label=_optional_str(data.get("protocol_label")),
            device_address=_optional_str(data.get("device_address")),
            signals=[UnknownSignal.from_dict(s) for s in signals_data],
            dismissed=bool(data.get("dismissed", False)),
            first_seen=data.get("first_seen") or utcnow_iso(),
            last_seen=data.get("last_seen") or utcnow_iso(),
            hit_count=int(data.get("hit_count", 0)),
            source=data.get("source", "sniffed"),
        )


# ---------------------------------------------------------------------------
# DeviceProfile — vendor-supplied template (SmartIR-style)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DeviceProfile:
    """A vendor device template.

    Profiles are immutable: they describe how a known device (TV, AC,
    fan, light) is wired, and they bundle the pulse commands needed to
    operate it. Profiles are loaded from JSON via ``DeviceProfile.from_dict``
    or programmatically constructed.
    """

    code: int
    category: EntityCategory
    manufacturer: str
    supported_models: tuple[str, ...]
    commands: dict[str, PulsePayload]
    speed_list: tuple[str, ...] | None = None
    matrix: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "category": str(self.category),
            "manufacturer": self.manufacturer,
            "supported_models": list(self.supported_models),
            "commands": {k: p.to_dict() for k, p in self.commands.items()},
            "speed_list": list(self.speed_list) if self.speed_list else None,
            "matrix": self.matrix,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceProfile:
        commands_data = data.get("commands") or {}
        if not isinstance(commands_data, dict):
            raise ValidationError("profile commands must be a dict")
        speed_list = data.get("speed_list")
        if speed_list is not None and not isinstance(speed_list, list):
            raise ValidationError("speed_list must be a list")
        return cls(
            code=int(_require(data, "code")),
            category=EntityCategory(data.get("category", EntityCategory.CUSTOM)),
            manufacturer=data.get("manufacturer", ""),
            supported_models=tuple(data.get("supported_models") or ()),
            commands={k: PulsePayload.from_dict(v) for k, v in commands_data.items()},
            speed_list=tuple(speed_list) if speed_list else None,
            matrix=data.get("matrix"),
        )


# ---------------------------------------------------------------------------
# RuneSnapshot — portable bundle for export/import
# ---------------------------------------------------------------------------

@dataclass
class RuneSnapshot:
    """A portable snapshot of RUNE state for export/import.

    Bumps ``snapshot_version`` whenever the on-disk schema changes in a
    way that requires migration on import.
    """

    snapshot_version: int
    devices: list[RuneDevice] = field(default_factory=list)
    actions: list[ActionBinding] = field(default_factory=list)
    created_at: str = field(default_factory=utcnow_iso)
    origin: str = ""

    CURRENT_VERSION = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_version": self.snapshot_version,
            "devices": [d.to_dict() for d in self.devices],
            "actions": [a.to_dict() for a in self.actions],
            "created_at": self.created_at,
            "origin": self.origin,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuneSnapshot:
        devices_data = data.get("devices") or []
        actions_data = data.get("actions") or []
        return cls(
            snapshot_version=int(data.get("snapshot_version", cls.CURRENT_VERSION)),
            devices=[RuneDevice.from_dict(d) for d in devices_data],
            actions=[ActionBinding.from_dict(a) for a in actions_data],
            created_at=data.get("created_at") or utcnow_iso(),
            origin=data.get("origin", ""),
        )


__all__ = [
    "ActionBinding",
    "ActionTarget",
    "DeviceProfile",
    "PulseCommand",
    "PulsePayload",
    "RuneDevice",
    "RuneSnapshot",
    "UnknownRemote",
    "UnknownSignal",
]

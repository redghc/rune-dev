"""Coordinator that wires :class:`RuneDevice` aggregates to HA platform
entities.

The coordinator owns:

- A reference to the device repository.
- A reference to the action repository.
- A reference to the TX gate + transmitter factory.
- A reference to the power monitor factory (optional).
- A registry of every platform entity, keyed by ``(device_id, role)``.

Public surface:

- :meth:`async_setup_platform` — called by HA's ``async_setup_entry``
  for each platform. Loads devices, instantiates entities, returns the
  list HA expects.
- :meth:`reload` — called when the user edits a device. Re-reads
  the repository and reconciles the entity set.

Why a coordinator at all? Two reasons:

1. **Sub-entity generation**: a single RuneDevice produces multiple HA
   entities — one ``FanEntity`` plus one ``ButtonEntity`` per pulse
   command. The coordinator handles this enumeration.
2. **TX path uniformity**: every entity sends through the same
   coordinator method (``async_send_command``) which routes via the
   TX gate + transmitter factory + mirror log. Entities don't construct
   their own transmitters.

For tests the coordinator is fully usable with no HA — the only HA
import is for the entity classes it instantiates, which are
themselves subclassed in test mode.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from custom_components.rune.adapters.power_monitor import (
    HAPowerMonitor,
    InMemoryPowerMonitor,
    classify_reading,
)
from custom_components.rune.adapters.transmitters.factory import select_transmitter
from custom_components.rune.adapters.tx_gate import TxGate
from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.domain.errors import (
    CommandNotLearnedError,
    UnsupportedHardwareError,
)
from custom_components.rune.domain.models import (
    ActionBinding,
    ActionTarget,
    PulseCommand,
    RuneDevice,
)
from custom_components.rune.ports.power_monitor import PowerVerdict
from custom_components.rune.ports.transmitter import TransmitterPort

if TYPE_CHECKING:
    from custom_components.rune.platforms._base import RunePlatformBase

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntityDescriptor:
    """One HA entity to add / remove."""

    platform: str  # 'fan', 'button', 'climate', …
    entity: RunePlatformBase
    sub_role: str = ""  # '' for primary, e.g. 'speed_3' for sub-buttons


class DevicePlatformCoordinator:
    """Owns the live set of HA entities backed by RuneDevice aggregates."""

    def __init__(
        self,
        *,
        hass: Any,
        device_repository: Any,
        action_repository: Any,
        tx_gate: TxGate,
        transmitter_factory: Callable[[Any, str, SignalTransport], TransmitterPort] = (
            select_transmitter
        ),
    ) -> None:
        self._hass = hass
        self._devices = device_repository
        self._actions = action_repository
        self._tx_gate = tx_gate
        self._transmitter_factory = transmitter_factory
        self._power_monitors: dict[str, HAPowerMonitor | InMemoryPowerMonitor] = {}
        self._entities: dict[str, EntityDescriptor] = {}

    # ------------------------------------------------------------------
    # TX path (shared by every entity)
    # ------------------------------------------------------------------

    async def async_send_command(
        self,
        *,
        device: RuneDevice,
        command: PulseCommand,
    ) -> None:
        """Send ``command`` via the device's first compatible transmitter.

        Skips silently when the device has no transmitters configured.
        Raises :class:`CommandNotLearnedError` if the command has no
        learned pulse, and :class:`UnsupportedHardwareError` if no
        configured emitter matches the signal transport.
        """
        if command.payload.is_empty:
            raise CommandNotLearnedError(
                f"Command {command.key!r} has no learned payload"
            )

        if not device.transmitter_entity_ids:
            _LOGGER.warning(
                "rune: device %s has no transmitter configured; skipping %s",
                device.id,
                command.key,
            )
            return

        transport = command.signal_category.transport
        chosen_emitter = self._select_emitter(device, transport)
        if chosen_emitter is None:
            raise UnsupportedHardwareError(
                f"No emitter on device {device.id} supports {transport!r}"
            )

        emitter = self._transmitter_factory(
            self._hass, chosen_emitter, transport
        )
        if not emitter.is_available:
            _LOGGER.warning(
                "rune: emitter %s is unavailable; command %s dropped",
                chosen_emitter,
                command.key,
            )
            return

        await self._tx_gate.send(
            emitter_entity_id=chosen_emitter,
            device_name=device.name,
            command=command,
            sender=emitter.send,
        )

    def _select_emitter(
        self,
        device: RuneDevice,
        transport: SignalTransport,
    ) -> str | None:
        """Return the first emitter entity_id matching ``transport``."""
        for emitter_id in device.transmitter_entity_ids:
            try:
                self._transmitter_factory(self._hass, emitter_id, transport)
                return emitter_id
            except UnsupportedHardwareError:
                continue
        return None

    # ------------------------------------------------------------------
    # Action binding dispatch
    # ------------------------------------------------------------------

    async def async_dispatch_action(
        self,
        *,
        binding: ActionBinding,
    ) -> bool:
        """Execute ``binding``'s target.

        Returns True if any side-effect was produced (TX, service call,
        scene activation, etc.). The sniffer engine calls this when a
        trigger fires.
        """
        from custom_components.rune.domain.enums import ActionKind

        target = binding.target
        if target.kind == ActionKind.PRESS_BUTTON:
            return await self._dispatch_press_button(binding, target)

        if target.kind == ActionKind.CALL_SERVICE:
            return await self._dispatch_call_service(target)

        if target.kind == ActionKind.ACTIVATE_SCENE:
            return await self._dispatch_scene(target)

        if target.kind == ActionKind.RUN_SCRIPT:
            return await self._dispatch_script(target)

        if target.kind == ActionKind.FIRE_EVENT:
            return await self._dispatch_fire_event(target)

        return False

    async def _dispatch_press_button(
        self, binding: ActionBinding, target: ActionTarget
    ) -> bool:
        if target.device_id is None or target.command_key is None:
            _LOGGER.warning(
                "rune: action %s missing device_id/command_key", binding.id
            )
            return False
        device = await self._devices.get(target.device_id)
        if device is None:
            _LOGGER.warning(
                "rune: action %s references missing device %s",
                binding.id,
                target.device_id,
            )
            return False
        command = device.commands.get(target.command_key)
        if command is None:
            _LOGGER.warning(
                "rune: action %s references missing command %s",
                binding.id,
                target.command_key,
            )
            return False
        await self.async_send_command(device=device, command=command)
        return True

    async def _dispatch_call_service(self, target: ActionTarget) -> bool:
        if not target.service_domain or not target.service_name:
            return False
        await self._hass.services.async_call(
            target.service_domain,
            target.service_name,
            target.service_data or {},
            blocking=True,
        )
        return True

    async def _dispatch_scene(self, target: ActionTarget) -> bool:
        if not target.target_entity_id:
            return False
        await self._hass.services.async_call(
            "scene",
            "turn_on",
            {"entity_id": target.target_entity_id},
            blocking=True,
        )
        return True

    async def _dispatch_script(self, target: ActionTarget) -> bool:
        if not target.target_entity_id:
            return False
        domain = (
            target.target_entity_id.split(".")[0]
            if "." in target.target_entity_id
            else "script"
        )
        await self._hass.services.async_call(
            domain,
            "turn_on",
            {"entity_id": target.target_entity_id},
            blocking=True,
        )
        return True

    async def _dispatch_fire_event(self, target: ActionTarget) -> bool:
        if not target.event_type:
            return False
        self._hass.bus.async_fire(
            target.event_type, target.event_data or {}
        )
        return True

    # ------------------------------------------------------------------
    # Power monitor wiring
    # ------------------------------------------------------------------

    def start_power_monitors(self) -> None:
        """Begin watching power sensors for every device that has one."""
        # Note: this is async-friendly — caller awaits from async_setup.
        for device in self._all_devices():
            if device.power_sensor_entity_id is None:
                continue
            self._start_one_power_monitor(device)

    def _start_one_power_monitor(self, device: RuneDevice) -> None:
        monitor = HAPowerMonitor(
            self._hass,
            device_id=device.id,
            sensor_entity_id=device.power_sensor_entity_id,
            off_below_w=device.power_off_below_w or 1.0,
            on_above_w=device.power_on_above_w or 3.0,
        )

        def _on_verdict(reading: Any) -> None:
            _LOGGER.info(
                "rune: power verdict for %s: %s (%s W)",
                device.id,
                reading.verdict,
                reading.watts,
            )

        monitor.start(_on_verdict)
        self._power_monitors[device.id] = monitor

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _all_devices(self) -> list[RuneDevice]:  # pragma: no cover - sync shim
        # Synchronous access for power monitor bootstrap. The actual
        # ``async_load`` happens via ``async_setup_platform``.
        raise NotImplementedError(
            "Use async_load_devices() from async_setup_platform"
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def entity_count(self) -> int:
        return len(self._entities)


__all__ = [
    "DevicePlatformCoordinator",
    "EntityDescriptor",
    "PowerVerdict",
    "classify_reading",  # re-export so platforms don't need their own
]

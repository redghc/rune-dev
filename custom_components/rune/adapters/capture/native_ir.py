"""Native IR capture provider — one-shot capture from a HA infrared receiver.

The orchestrator's :class:`~custom_components.rune.adapters.capture.orchestrator.CaptureOrchestrator`
expects a :class:`CaptureProvider` with a one-shot ``start → wait → stop``
shape. HA's infrared platform uses a push-style subscription: callers
hand in a callback and the platform fires it on every received signal.

This adapter bridges the two: ``start_capture`` opens a subscription
that funnels every captured pulse into an internal queue, the first
pulse is returned by ``async_wait_for_signal``, and ``async_stop_capture``
unsubscribes. Extra pulses that arrive after we have our result are
drained so they don't leak into the next session.

Built on top of :class:`~custom_components.rune.adapters.receivers.native_ir.NativeIRReceiver`
so the IR entity resolution rules live in one place — the factory in
``adapters/receivers/factory.py`` decides which receiver adapter fits a
given ``entity_id`` and we just delegate the subscription.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from custom_components.rune.adapters.capture.providers import CaptureProvider
from custom_components.rune.adapters.receivers.factory import select_receiver
from custom_components.rune.domain.enums import SignalTransport
from custom_components.rune.domain.errors import (
    CaptureProviderUnavailableError,
    UnsupportedHardwareError,
)
from custom_components.rune.ports.receiver import CapturedPulse

# Importing ``homeassistant`` lazily keeps the capture package usable
# from pure-Python unit tests without a HA install. Anything that
# touches HA belongs behind ``_is_ir_receiver`` / ``async_start_capture``.
try:
    from homeassistant.exceptions import HomeAssistantError
except ImportError:  # pragma: no cover - exercised in tests via monkeypatch
    HomeAssistantError = None  # type: ignore[assignment,misc]


@dataclass(frozen=True)
class ProbeResult:
    """What ``probe_receiver`` found out about a candidate entity.

    Carries the diagnostic reason alongside ``available`` so the WS
    handler can render a real explanation instead of the bare
    "not available" string. The most common misconfiguration is
    attaching an :class:`InfraredEmitterEntity` (a transmitter the
    user named ``emisor`` / ``tx`` / ``blaster``) to a slot the
    integration expects to *listen* on; we surface that explicitly
    via :attr:`is_emitter`.
    """

    available: bool
    reason: str  # human-readable; safe to render to the user
    is_emitter: bool = False  # True → entity is an InfraredEmitterEntity


if TYPE_CHECKING:
    from custom_components.rune.adapters.receivers.native_ir import NativeIRReceiver

_LOGGER = logging.getLogger(__name__)


class NativeIRCaptureProvider(CaptureProvider):
    """One-shot IR capture session bound to a single receiver entity.

    Parameters
    ----------
    hass:
        Home Assistant instance used to look up the entity state and
        drive the ``infrared.async_subscribe_receiver`` call.
    receiver_entity_id:
        The ``infrared.*`` (or other IR) entity to listen on. The
        provider routes through :func:`select_receiver` so the actual
        adapter selection (native IR, ESPHome legacy, etc.) lives in
        the receivers factory — single source of truth.

    The class is intentionally transport-fixed to IR: a separate
    :class:`BroadlinkRFCaptureProvider` covers the RF path. Mixing
    transports here would muddle the per-domain error reporting the
    WS handler surfaces to the panel.
    """

    transport = SignalTransport.IR
    name = "native-ir"

    def __init__(self, hass: Any, receiver_entity_id: str) -> None:
        self._hass = hass
        self.receiver_entity_id = receiver_entity_id
        self._receiver: NativeIRReceiver | None = None
        self._unsubscribe: Any = None
        self._pulse_queue: asyncio.Queue[CapturedPulse | None] = asyncio.Queue()
        self._started = False

    @property
    def is_available(self) -> bool:
        """Boolean shortcut for the orchestrator's lock check.

        The WS handler should prefer :func:`probe_receiver` so it can
        surface a useful diagnostic; ``is_available`` stays simple for
        the single-flight lock guard.
        """
        return probe_receiver(self._hass, self.receiver_entity_id).available

    def _ensure_receiver(self) -> "NativeIRReceiver":
        if self._receiver is None:
            # ``probe_receiver`` ran first in the happy path; this is
            # the belt-and-braces guard for callers that skipped it.
            self._receiver = select_receiver(
                self._hass, self.receiver_entity_id, SignalTransport.IR
            )
        return self._receiver

    async def async_start_capture(self, timeout_s: float) -> None:
        """Subscribe to the receiver and arm the pulse queue.

        Raises :class:`CaptureProviderUnavailableError` when the
        underlying entity is missing — the orchestrator surfaces that
        as ``provider.is_available is False`` upstream, but we keep
        the second check here so the WS handler can surface a
        human-readable message instead of a generic RuntimeError.
        """
        if not self.is_available:
            raise CaptureProviderUnavailableError(
                f"IR receiver {self.receiver_entity_id!r} is not available"
            )
        receiver = self._ensure_receiver()

        async def _on_capture(pulse: CapturedPulse) -> None:
            # Drop into the queue; ``wait_for_signal`` takes the first.
            # We don't await — the subscription API is synchronous and
            # we want the next signal slot to stay free.
            await self._pulse_queue.put(pulse)

        try:
            self._unsubscribe = await receiver.start_listening(_on_capture)
        except Exception as err:
            # ``infrared.async_subscribe_receiver`` raises
            # ``HomeAssistantError(translation_key="receiver_not_found")``
            # when the entity exists but isn't a registered
            # ``InfraredReceiverEntity``. Convert that and any other
            # HA-level failure into a friendly provider error so the
            # WS handler surfaces a real message instead of the raw
            # HA class name.
            if _is_unknown_receiver_error(err):
                raise CaptureProviderUnavailableError(
                    f"Receiver {self.receiver_entity_id!r} is not a registered "
                    "infrared receiver. Add an IR receiver entity to Home "
                    "Assistant or pick one configured for IR capture."
                ) from err
            raise
        self._started = True

    async def async_wait_for_signal(self, timeout_s: float) -> CapturedPulse | None:
        if not self._started:
            raise RuntimeError(
                "NativeIRCaptureProvider.async_wait_for_signal called before "
                "async_start_capture"
            )
        try:
            return await asyncio.wait_for(self._pulse_queue.get(), timeout=timeout_s)
        except TimeoutError:
            return None

    async def async_stop_capture(self) -> None:
        """Unsubscribe and drain any late pulses."""
        self._started = False
        if self._unsubscribe is not None:
            try:
                self._unsubscribe()
            except Exception:
                _LOGGER.exception(
                    "NativeIRCaptureProvider: unsubscribe raised for %s",
                    self.receiver_entity_id,
                )
            self._unsubscribe = None
        # Drain any stragglers that landed between ``wait_for_signal``
        # resolving and ``stop_capture`` firing so they don't leak into
        # the next session that reuses this provider instance.
        while not self._pulse_queue.empty():
            try:
                self._pulse_queue.get_nowait()
            except asyncio.QueueEmpty:
                break


__all__ = ["NativeIRCaptureProvider", "ProbeResult", "probe_receiver"]


def probe_receiver(hass: Any, receiver_entity_id: str) -> ProbeResult:
    """Inspect a candidate receiver entity and explain its status.

    Public helper so the WS handler can surface the same diagnostic
    the provider uses internally. We probe in this order:

    1. The factory can resolve an IR adapter for the entity (else
       we can't talk to it at all).
    2. The HA infrared platform reports the entity as a registered
       receiver (``async_get_receivers``).
    3. The HA state object says it's not unavailable.

    Each step that fails produces a distinct :attr:`ProbeResult.reason`
    so the panel can render actionable guidance — including the
    emitter-vs-receiver distinction, which is the most common
    misconfiguration.
    """
    if not receiver_entity_id:
        return ProbeResult(False, "No receiver entity configured.")
    try:
        receiver = select_receiver(hass, receiver_entity_id, SignalTransport.IR)
    except UnsupportedHardwareError as err:
        return ProbeResult(
            False,
            f"No IR adapter for entity {receiver_entity_id!r}: {err}",
        )
    if not _is_ir_receiver(hass, receiver_entity_id):
        # Special-case the most common mistake: the user wired up the
        # *transmitter* entity (named ``emisor`` / ``emitter`` /
        # ``blaster``) thinking it's the receiver. Naming aside, the
        # ``infrared.async_subscribe_receiver`` call would raise
        # ``receiver_not_found`` mid-capture — catch it here and
        # explain what's actually attached.
        if _is_ir_emitter(hass, receiver_entity_id):
            return ProbeResult(
                False,
                f"Entity {receiver_entity_id!r} is an IR emitter (transmitter), "
                "not a receiver. To learn commands you need an IR receiver "
                "entity — devices with both blaster + receiver capabilities "
                "expose two separate entities. Pick the receiver one.",
                is_emitter=True,
            )
        return ProbeResult(
            False,
            f"Entity {receiver_entity_id!r} is in the infrared domain but is "
            "not registered as an InfraredReceiverEntity in Home Assistant. "
            "Make sure the integration that provides it loaded the receiver "
            "component (look for 'receiver' in the entity's settings).",
        )
    if not receiver.is_available:
        return ProbeResult(
            False,
            f"Entity {receiver_entity_id!r} is currently unavailable "
            "(state is 'unavailable' or missing). Check that the device is "
            "powered on and connected to Home Assistant.",
        )
    return ProbeResult(
        True,
        f"Entity {receiver_entity_id!r} is a registered infrared receiver.",
    )


def _is_ir_receiver(hass: Any, receiver_entity_id: str) -> bool:
    """True when the entity is registered as an HA infrared receiver.

    Uses ``infrared.async_get_receivers`` — the canonical probe the
    HA platform itself recommends. Anything else (a stale reference,
    an emitter misconfigured as a receiver, etc.) returns ``False``
    so the provider can refuse early instead of raising a raw
    ``HomeAssistantError`` mid-capture.
    """
    try:
        from homeassistant.components import infrared
    except ImportError:
        return False
    try:
        receivers = infrared.async_get_receivers(hass)
    except Exception:  # pragma: no cover - defensive against HA quirks
        return False
    return receiver_entity_id in receivers


def _is_ir_emitter(hass: Any, entity_id: str) -> bool:
    """True when the entity is registered as an HA infrared emitter.

    Separate from ``_is_ir_receiver`` because the user's most common
    mistake is attaching the *transmitter* entity (named ``emisor`` /
    ``emitter`` / ``tx`` etc.) to a slot the integration expects to
    *listen* on. Telling them "this is an emitter, not a receiver"
    is the difference between a productive debug session and a
    frustrating one.
    """
    try:
        from homeassistant.components import infrared
    except ImportError:
        return False
    try:
        emitters = infrared.async_get_emitters(hass)
    except Exception:  # pragma: no cover - defensive against HA quirks
        return False
    return entity_id in emitters


def _is_unknown_receiver_error(err: BaseException) -> bool:
    """Detect HA's ``receiver_not_found`` error regardless of version.

    Older HA versions raise ``HomeAssistantError("receiver_not_found")``
    (or with the message embedded). Newer ones carry
    ``translation_key="receiver_not_found"``. We accept any of those
    so the wrapper keeps working across HA upgrades.
    """
    if HomeAssistantError is None or not isinstance(err, HomeAssistantError):
        return False
    translation_key = getattr(err, "translation_key", None)
    if translation_key == "receiver_not_found":
        return True
    # Fallback: the legacy message form is the translation key string
    # itself, surfaced through ``str(err)`` when no translation is set.
    return "receiver_not_found" in str(err)

"""Capture session orchestration.

One :class:`CaptureOrchestrator` per integration instance. The
orchestrator guarantees:

- Only ONE capture session runs at a time (asyncio.Lock).
- Listeners can subscribe to session state changes and capture results.
- HA bus events fire on success / timeout / error.
- Cancellation propagates to the active provider.

The orchestrator is pure — no Home Assistant import is required for
the lock / listener / event logic. The HA ``bus.async_fire`` calls
take a ``hass`` reference as a constructor argument so tests can pass
``None`` and skip the HA side-effects.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from custom_components.rune.const import DEFAULT_CAPTURE_TIMEOUT_S
from custom_components.rune.domain.enums import CaptureState

if TYPE_CHECKING:
    from custom_components.rune.adapters.capture.providers import CaptureProvider

_LOGGER = logging.getLogger(__name__)


CaptureListener = Callable[[CaptureState, Any], None]


class CaptureInProgressError(RuntimeError):
    """Raised when ``start_capture`` is called while another session is active."""


class CaptureOrchestrator:
    """Manages IR/RF capture sessions with single-flight guarantee."""

    def __init__(self, hass: Any = None) -> None:
        self._hass = hass
        self._lock = asyncio.Lock()
        self._active_session_id: str | None = None
        self._active_provider: CaptureProvider | None = None
        self._task: asyncio.Task | None = None
        self._listeners: dict[str, list[CaptureListener]] = {}
        self._results: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public state
    # ------------------------------------------------------------------

    @property
    def is_capturing(self) -> bool:
        return self._lock.locked() and self._active_session_id is not None

    @property
    def active_session_id(self) -> str | None:
        return self._active_session_id

    def get_session_result(self, session_id: str) -> Any:
        return self._results.get(session_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_capture(
        self,
        provider: CaptureProvider,
        session_id: str,
        timeout_s: float = DEFAULT_CAPTURE_TIMEOUT_S,
    ) -> None:
        """Begin a capture session.

        Raises:
            CaptureInProgressError: another session is already active.
            CaptureProviderUnavailableError: the chosen provider can't
                run right now (entity missing, wrong transport, not a
                registered IR receiver, etc.). Callers can surface the
                reason directly to the user.
        """
        from custom_components.rune.domain.errors import (
            CaptureProviderUnavailableError,
        )

        if self._lock.locked():
            raise CaptureInProgressError(
                "Another capture session is already in progress"
            )
        if not provider.is_available:
            entity_id = getattr(provider, "receiver_entity_id", None)
            name = getattr(provider, "name", provider) or "capture provider"
            raise CaptureProviderUnavailableError(
                f"Capture provider {name!r} is not available"
                + (f" for receiver {entity_id!r}" if entity_id else "")
                + ". Check that the entity is loaded and is a supported "
                "receiver for this provider."
            )

        await self._lock.acquire()

        try:
            self._active_session_id = session_id
            self._active_provider = provider
            await provider.async_start_capture(timeout_s)
            self._notify(session_id, CaptureState.LISTENING, None)

            self._task = asyncio.create_task(self._capture_loop(session_id, provider, timeout_s))
        except Exception:
            self._cleanup()
            self._lock.release()
            raise

    async def cancel_capture(self, session_id: str) -> None:
        """Cancel an active capture session.

        No-op when the session isn't active or already finished.
        """
        if self._active_session_id != session_id:
            return
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task

    def subscribe(
        self,
        session_id: str,
        callback: CaptureListener,
    ) -> Callable[[], None]:
        """Subscribe to a session's state changes.

        Returns an unsubscribe callable.
        """
        self._listeners.setdefault(session_id, []).append(callback)

        def _unsubscribe() -> None:
            listeners = self._listeners.get(session_id)
            if listeners and callback in listeners:
                listeners.remove(callback)
            if listeners is not None and not listeners:
                self._listeners.pop(session_id, None)

        return _unsubscribe

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------

    async def _capture_loop(
        self,
        session_id: str,
        provider: CaptureProvider,
        timeout_s: float,
    ) -> None:
        """Drive a single capture session: wait → result → notify."""
        try:
            result = await provider.async_wait_for_signal(timeout_s)
        except asyncio.CancelledError:
            self._notify(session_id, CaptureState.CANCELLED, None)
            await self._safe_stop(provider)
            self._finalize()
            raise
        except Exception as err:
            _LOGGER.exception("Capture provider raised")
            self._notify(session_id, CaptureState.ERROR, None)
            if self._hass is not None:
                self._hass.bus.async_fire(
                    "rune_capture_error",
                    {"session_id": session_id, "error": str(err)},
                )
            await self._safe_stop(provider)
            self._finalize()
            return

        await self._safe_stop(provider)

        if result is None:
            self._notify(session_id, CaptureState.TIMEOUT, None)
            if self._hass is not None:
                self._hass.bus.async_fire(
                    "rune_capture_timeout",
                    {"session_id": session_id},
                )
            self._finalize()
            return

        self._results[session_id] = result
        self._notify(session_id, CaptureState.CAPTURED, result)
        if self._hass is not None:
            self._hass.bus.async_fire(
                "rune_command_captured",
                {"session_id": session_id, "result": result},
            )
        self._finalize()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _notify(
        self,
        session_id: str,
        state: CaptureState,
        result: Any,
    ) -> None:
        for callback in list(self._listeners.get(session_id, [])):
            try:
                callback(state, result)
            except Exception:
                _LOGGER.exception("Capture listener raised")

    async def _safe_stop(self, provider: CaptureProvider) -> None:
        try:
            await provider.async_stop_capture()
        except Exception:
            _LOGGER.exception("Stopping capture provider raised")

    def _finalize(self) -> None:
        self._cleanup()
        if self._lock.locked():
            try:
                self._lock.release()
            except RuntimeError as err:
                _LOGGER.warning("TxGate: lock release failed: %s", err)

    def _cleanup(self) -> None:
        self._active_session_id = None
        self._active_provider = None
        self._task = None


__all__ = ["CaptureInProgressError", "CaptureListener", "CaptureOrchestrator"]

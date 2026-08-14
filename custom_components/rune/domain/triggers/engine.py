"""Trigger engine — decides whether an incoming signal fires an action.

State machine per ``(binding_id, signal_id)``:

- A press arriving within ``TRIGGER_HIT_RESET_WINDOW_S`` of the FIRST
  press in the current chain increments the hit count.
- A press arriving after the window closes starts a fresh chain and
  counts as its first hit.
- When hit count reaches ``min_hits`` and the chain is still inside
  the window, the engine fires the binding's ``ActionTarget`` exactly
  once.
- Multi-receiver dedup: a second capture from a different receiver
  within ``MULTI_RECEIVER_DEDUP_WINDOW_S`` of the first is the SAME
  press, not a new one — no second hit increment.
- Receiver scope: if the binding lists specific receiver entity ids,
  only captures from those receivers can increment or fire.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from custom_components.rune.const import (
    MULTI_RECEIVER_DEDUP_WINDOW_S,
    TRIGGER_HIT_RESET_WINDOW_S,
)
from custom_components.rune.domain.models import ActionBinding


@dataclass
class _HitState:
    """Per-``(binding, signal)`` hit accumulator."""

    hit_count: int = 0
    first_hit_monotonic: float = 0.0
    last_hit_monotonic: float = 0.0
    fired: bool = False

    def record_hit(self, now: float) -> bool:
        """Record a press; return True if the trigger should fire.

        Side effect: resets the window when the chain has expired.
        """
        if now - self.first_hit_monotonic > TRIGGER_HIT_RESET_WINDOW_S:
            self.hit_count = 0
            self.first_hit_monotonic = now
            self.fired = False
        if self.hit_count == 0:
            self.first_hit_monotonic = now
        self.hit_count += 1
        self.last_hit_monotonic = now
        return False

    def reset(self) -> None:
        self.hit_count = 0
        self.first_hit_monotonic = 0.0
        self.last_hit_monotonic = 0.0
        self.fired = False


@dataclass
class TriggerDecision:
    """Outcome of evaluating one incoming capture against the binding catalog."""

    binding_id: str
    should_fire: bool
    receiver_entity_id: str | None


class TriggerEngine:
    """Evaluate captures against action bindings and emit fire decisions.

    Stateful: the engine carries the per-``(binding, signal)`` hit
    counters across calls. Use :meth:`reset` to clear state, and
    :meth:`reset_binding` to clear one binding's state.
    """

    def __init__(
        self,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._monotonic = monotonic
        self._hit_states: dict[tuple[str, str], _HitState] = {}
        self._last_capture_per_signal: dict[str, tuple[float, str | None]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        binding: ActionBinding,
        signal_id: str,
        *,
        receiver_entity_id: str | None,
    ) -> TriggerDecision:
        """Decide whether ``binding`` should fire for a capture of ``signal_id``.

        The capture is considered to have arrived ``now`` (monotonic).
        Returns a :class:`TriggerDecision` whose ``should_fire`` is True
        exactly when this call should trigger an action.
        """
        if not binding.enabled:
            return TriggerDecision(binding.id, False, receiver_entity_id)
        if binding.signal_id != signal_id:
            return TriggerDecision(binding.id, False, receiver_entity_id)
        if not self._receiver_matches(binding, receiver_entity_id):
            return TriggerDecision(binding.id, False, receiver_entity_id)
        if self._is_same_physical_press(signal_id, receiver_entity_id):
            return TriggerDecision(binding.id, False, receiver_entity_id)

        state = self._state_for(binding.id, signal_id)
        now = self._monotonic()
        state.record_hit(now)
        should_fire = state.hit_count >= binding.min_hits and not state.fired
        if should_fire:
            state.fired = True
        self._remember_capture(signal_id, receiver_entity_id)
        return TriggerDecision(binding.id, should_fire, receiver_entity_id)

    def reset(self) -> None:
        """Clear all state — useful in tests and after a settings change."""
        self._hit_states.clear()
        self._last_capture_per_signal.clear()

    def reset_binding(self, binding_id: str) -> None:
        """Clear state for one binding."""
        keys_to_drop = [k for k in self._hit_states if k[0] == binding_id]
        for key in keys_to_drop:
            self._hit_states.pop(key, None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _state_for(self, binding_id: str, signal_id: str) -> _HitState:
        key = (binding_id, signal_id)
        state = self._hit_states.get(key)
        if state is None:
            state = _HitState()
            self._hit_states[key] = state
        return state

    @staticmethod
    def _receiver_matches(binding: ActionBinding, receiver_entity_id: str | None) -> bool:
        """True when the receiver is in scope (or scope is empty)."""
        if not binding.receiver_entity_ids:
            return True
        if receiver_entity_id is None:
            return False
        return receiver_entity_id in binding.receiver_entity_ids

    def _is_same_physical_press(self, signal_id: str, receiver_entity_id: str | None) -> bool:
        """True if the previous capture for ``signal_id`` is recent enough to dedup."""
        previous = self._last_capture_per_signal.get(signal_id)
        if previous is None:
            return False
        previous_at, previous_receiver = previous
        if previous_receiver == receiver_entity_id:
            return False
        elapsed = self._monotonic() - previous_at
        return elapsed <= MULTI_RECEIVER_DEDUP_WINDOW_S

    def _remember_capture(self, signal_id: str, receiver_entity_id: str | None) -> None:
        self._last_capture_per_signal[signal_id] = (self._monotonic(), receiver_entity_id)


__all__ = ["TriggerDecision", "TriggerEngine"]

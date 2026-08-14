"""Tests for the trigger engine."""
from __future__ import annotations

from custom_components.rune.domain.models import ActionBinding, ActionTarget
from custom_components.rune.domain.triggers.engine import TriggerEngine


def _binding(
    *,
    binding_id: str = "b1",
    signal_id: str = "s1",
    min_hits: int = 1,
    receiver_scope: list[str] | None = None,
    enabled: bool = True,
) -> ActionBinding:
    return ActionBinding(
        id=binding_id,
        name="test",
        signal_id=signal_id,
        target=ActionTarget(kind="press_button", device_id="d1", command_key="power"),
        min_hits=min_hits,
        receiver_entity_ids=list(receiver_scope) if receiver_scope else [],
        enabled=enabled,
    )


class TestBasicFire:
    def test_single_hit_fires_when_min_hits_is_one(self) -> None:
        engine = TriggerEngine()
        binding = _binding(min_hits=1)
        decision = engine.evaluate(binding, "s1", receiver_entity_id=None)
        assert decision.should_fire is True

    def test_single_hit_does_not_fire_when_min_hits_is_two(self) -> None:
        engine = TriggerEngine()
        binding = _binding(min_hits=2)
        decision = engine.evaluate(binding, "s1", receiver_entity_id=None)
        assert decision.should_fire is False

    def test_second_hit_fires_at_min_hits_two(self) -> None:
        engine = TriggerEngine()
        binding = _binding(min_hits=2)
        first = engine.evaluate(binding, "s1", receiver_entity_id=None)
        second = engine.evaluate(binding, "s1", receiver_entity_id=None)
        assert first.should_fire is False
        assert second.should_fire is True


class TestFiresOnlyOncePerChain:
    def test_three_hits_fire_only_once(self) -> None:
        engine = TriggerEngine()
        binding = _binding(min_hits=2)
        results = [
            engine.evaluate(binding, "s1", receiver_entity_id=None).should_fire
            for _ in range(3)
        ]
        # First two: only second fires. Third must NOT re-fire.
        assert results == [False, True, False]

    def test_new_chain_can_fire_again(self) -> None:
        engine = TriggerEngine()
        binding = _binding(min_hits=1)
        # First chain fires.
        assert engine.evaluate(binding, "s1", receiver_entity_id=None).should_fire
        # Reset window manually to simulate a long gap.
        engine.reset_binding(binding.id)
        # Second chain fires too.
        assert engine.evaluate(binding, "s1", receiver_entity_id=None).should_fire


class TestResetWindow:
    def test_window_expiry_starts_fresh_chain(self) -> None:
        # Use a synthetic clock that we advance past the reset window.
        clock = {"t": 0.0}

        def now() -> float:
            return clock["t"]

        engine = TriggerEngine(monotonic=now)
        binding = _binding(min_hits=2)
        # First hit at t=0.
        engine.evaluate(binding, "s1", receiver_entity_id=None)
        # Advance well past TRIGGER_HIT_RESET_WINDOW_S (5s).
        clock["t"] = 10.0
        # Now this hit should restart the chain — count is back to 0/1.
        decision = engine.evaluate(binding, "s1", receiver_entity_id=None)
        # 1 hit on fresh chain, min_hits=2 → no fire.
        assert decision.should_fire is False


class TestMultiReceiverDedup:
    def test_same_signal_from_two_receivers_within_window_dedups(self) -> None:
        clock = {"t": 0.0}
        engine = TriggerEngine(monotonic=lambda: clock["t"])
        binding = _binding(min_hits=1)
        # Receiver A.
        first = engine.evaluate(binding, "s1", receiver_entity_id="remote.a")
        assert first.should_fire is True
        # Receiver B arrives within the dedup window — same physical press.
        clock["t"] = 0.05
        second = engine.evaluate(binding, "s1", receiver_entity_id="remote.b")
        # Must NOT re-fire (deduped as same press).
        assert second.should_fire is False

    def test_same_receiver_does_not_dedup(self) -> None:
        clock = {"t": 0.0}
        engine = TriggerEngine(monotonic=lambda: clock["t"])
        binding = _binding(min_hits=1)
        # Same receiver hits twice within window — that's two presses,
        # not one physical press captured twice.
        first = engine.evaluate(binding, "s1", receiver_entity_id="remote.a")
        clock["t"] = 0.05
        second = engine.evaluate(binding, "s1", receiver_entity_id="remote.a")
        assert first.should_fire is True
        # Already fired in chain — won't re-fire anyway.
        assert second.should_fire is False

    def test_after_dedup_window_can_fire(self) -> None:
        clock = {"t": 0.0}
        engine = TriggerEngine(monotonic=lambda: clock["t"])
        binding = _binding(min_hits=1)
        engine.evaluate(binding, "s1", receiver_entity_id="remote.a")
        # Advance past dedup window.
        clock["t"] = 1.0
        engine.reset_binding(binding.id)
        decision = engine.evaluate(binding, "s1", receiver_entity_id="remote.b")
        assert decision.should_fire is True


class TestReceiverScope:
    def test_unscoped_binding_matches_any_receiver(self) -> None:
        engine = TriggerEngine()
        binding = _binding(receiver_scope=None)
        assert engine.evaluate(binding, "s1", receiver_entity_id="any").should_fire is True

    def test_scoped_binding_rejects_other_receiver(self) -> None:
        engine = TriggerEngine()
        binding = _binding(receiver_scope=["remote.kitchen"])
        decision = engine.evaluate(binding, "s1", receiver_entity_id="remote.bedroom")
        assert decision.should_fire is False
        assert decision.receiver_entity_id == "remote.bedroom"

    def test_scoped_binding_rejects_none_receiver(self) -> None:
        engine = TriggerEngine()
        binding = _binding(receiver_scope=["remote.kitchen"])
        decision = engine.evaluate(binding, "s1", receiver_entity_id=None)
        assert decision.should_fire is False

    def test_scoped_binding_accepts_listed_receiver(self) -> None:
        engine = TriggerEngine()
        binding = _binding(receiver_scope=["remote.kitchen"])
        decision = engine.evaluate(binding, "s1", receiver_entity_id="remote.kitchen")
        assert decision.should_fire is True


class TestDisabled:
    def test_disabled_binding_never_fires(self) -> None:
        engine = TriggerEngine()
        binding = _binding(enabled=False)
        decision = engine.evaluate(binding, "s1", receiver_entity_id=None)
        assert decision.should_fire is False


class TestSignalIdMismatch:
    def test_different_signal_id_does_not_match(self) -> None:
        engine = TriggerEngine()
        binding = _binding(signal_id="s1")
        decision = engine.evaluate(binding, "s2", receiver_entity_id=None)
        assert decision.should_fire is False


class TestReset:
    def test_reset_clears_all_state(self) -> None:
        engine = TriggerEngine()
        binding = _binding()
        engine.evaluate(binding, "s1", receiver_entity_id=None)
        engine.reset()
        # After reset, the binding should be able to fire again.
        decision = engine.evaluate(binding, "s1", receiver_entity_id=None)
        assert decision.should_fire is True

    def test_reset_binding_clears_only_one(self) -> None:
        engine = TriggerEngine()
        b1 = _binding(binding_id="b1")
        b2 = _binding(binding_id="b2")
        engine.evaluate(b1, "s1", receiver_entity_id=None)
        engine.evaluate(b2, "s1", receiver_entity_id=None)
        engine.reset_binding("b1")
        # b2 was fired; should NOT re-fire (still in chain).
        # b1 was reset; first hit should fire.
        assert engine.evaluate(b1, "s1", receiver_entity_id=None).should_fire is True
        assert engine.evaluate(b2, "s1", receiver_entity_id=None).should_fire is False

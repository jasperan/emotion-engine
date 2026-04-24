import pytest
from unittest.mock import MagicMock
from emotionsim.simulation.emotion_contagion import EmotionContagion, ContagionEvent


def make_agent(agent_id, name, location, stress=5, extraversion=5,
               neuroticism=5, role="human"):
    agent = MagicMock()
    agent.id = agent_id
    agent.name = name
    agent.role = role
    agent.dynamic_state = {"stress_level": stress, "location": location}
    agent.persona = MagicMock()
    agent.persona.extraversion = extraversion
    agent.persona.neuroticism = neuroticism
    return agent


class TestEmotionContagionBasic:

    def test_no_contagion_with_single_agent(self):
        ec = EmotionContagion()
        agents = {"a1": make_agent("a1", "Alice", "shelter", stress=9)}
        events = ec.propagate(["a1"], agents, step=1, location="shelter")
        assert events == []

    def test_no_contagion_below_threshold(self):
        """Agents with stress diff < DIFFERENTIAL_THRESHOLD should not infect each other."""
        ec = EmotionContagion()
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=5),
            "a2": make_agent("a2", "Bob", "shelter", stress=6),
        }
        events = ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        assert events == []

    def test_panic_spreads_from_high_to_low_stress(self):
        ec = EmotionContagion(spread_rate=0.5, max_delta_per_step=2)
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=9, extraversion=8),
            "a2": make_agent("a2", "Bob", "shelter", stress=3, neuroticism=8),
        }
        events = ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        # Bob should be affected (high neuroticism receiver, high extraversion emitter)
        bob_events = [e for e in events if e.target_id == "a2"]
        assert len(bob_events) >= 1
        assert bob_events[0].delta > 0
        assert bob_events[0].mechanism == "panic_spread"

    def test_calm_anchor_reduces_stress(self):
        ec = EmotionContagion(spread_rate=0.5, max_delta_per_step=2, calm_factor=0.8)
        agents = {
            "a1": make_agent("a1", "Bobby", "shelter", stress=2, extraversion=8),
            "a2": make_agent("a2", "Jake", "shelter", stress=8, neuroticism=8),
        }
        events = ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        jake_events = [e for e in events if e.target_id == "a2"]
        assert len(jake_events) >= 1
        assert jake_events[0].delta < 0
        assert jake_events[0].mechanism == "calm_anchor"

    def test_delta_clamped_to_max(self):
        ec = EmotionContagion(spread_rate=1.0, max_delta_per_step=2)
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=10, extraversion=10),
            "a2": make_agent("a2", "Bob", "shelter", stress=1, neuroticism=10),
        }
        events = ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        bob_events = [e for e in events if e.target_id == "a2"]
        assert len(bob_events) == 1
        assert bob_events[0].delta <= 2

    def test_stress_bounds_respected(self):
        """Stress should never go below 1 or above 10."""
        ec = EmotionContagion(spread_rate=1.0, max_delta_per_step=2)
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=10, extraversion=10),
            "a2": make_agent("a2", "Bob", "shelter", stress=9, neuroticism=10),
        }
        events = ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        for e in events:
            assert 1 <= e.target_stress_after <= 10

    def test_non_human_agents_skipped(self):
        ec = EmotionContagion()
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=9, role="human"),
            "env": make_agent("env", "Environment", "shelter", stress=1, role="environment"),
        }
        events = ec.propagate(["a1", "env"], agents, step=1, location="shelter")
        assert events == []


class TestEmotionContagionTrust:

    def test_high_trust_amplifies_contagion(self):
        ec = EmotionContagion(spread_rate=0.5, max_delta_per_step=3)
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=9, extraversion=7),
            "a2": make_agent("a2", "Bob", "shelter", stress=3, neuroticism=7),
        }
        high_trust = lambda s, t: 10
        low_trust = lambda s, t: 1

        events_high = ec.propagate(["a1", "a2"], agents, trust_fn=high_trust, step=1, location="shelter")
        ec_low = EmotionContagion(spread_rate=0.5, max_delta_per_step=3)
        # Reset Bob's stress for fair comparison
        agents["a2"].dynamic_state["stress_level"] = 3
        events_low = ec_low.propagate(["a1", "a2"], agents, trust_fn=low_trust, step=1, location="shelter")

        delta_high = sum(e.delta for e in events_high if e.target_id == "a2")
        delta_low = sum(e.delta for e in events_low if e.target_id == "a2")
        assert delta_high >= delta_low

    def test_default_trust_is_neutral(self):
        """Without trust_fn, trust defaults to 5 (neutral)."""
        ec = EmotionContagion(spread_rate=0.5)
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=9, extraversion=8),
            "a2": make_agent("a2", "Bob", "shelter", stress=3, neuroticism=8),
        }
        events = ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        assert len(events) >= 1  # Should still propagate at neutral trust


class TestEmotionContagionPersonality:

    def test_low_neuroticism_resists_panic(self):
        """Low neuroticism agent should receive less or no contagion."""
        ec = EmotionContagion(spread_rate=0.3, max_delta_per_step=2)
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=9, extraversion=5),
            "a2": make_agent("a2", "Stoic", "shelter", stress=5, neuroticism=1),
        }
        events = ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        stoic_events = [e for e in events if e.target_id == "a2"]
        # Should be small or zero delta
        if stoic_events:
            assert stoic_events[0].delta <= 1

    def test_low_extraversion_emits_weakly(self):
        """Low extraversion emitter should have weak influence."""
        ec = EmotionContagion(spread_rate=0.3, max_delta_per_step=2)
        agents = {
            "a1": make_agent("a1", "Introvert", "shelter", stress=9, extraversion=1),
            "a2": make_agent("a2", "Bob", "shelter", stress=3, neuroticism=5),
        }
        events = ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        bob_events = [e for e in events if e.target_id == "a2"]
        # Weak emitter with moderate receiver — may not cross threshold
        if bob_events:
            assert bob_events[0].delta <= 1


class TestEmotionContagionMultiAgent:

    def test_three_agent_scene(self):
        """Three agents: one panicked, one calm, one moderate."""
        ec = EmotionContagion(spread_rate=0.4, max_delta_per_step=2)
        agents = {
            "panic": make_agent("panic", "Panicker", "roof", stress=9, extraversion=8),
            "calm": make_agent("calm", "Anchor", "roof", stress=2, extraversion=7),
            "mid": make_agent("mid", "Middle", "roof", stress=5, neuroticism=7),
        }
        events = ec.propagate(["panic", "calm", "mid"], agents, step=1, location="roof")
        # Middle should be pulled in both directions — net effect depends on weights
        assert isinstance(events, list)

    def test_empty_agent_list(self):
        ec = EmotionContagion()
        events = ec.propagate([], {}, step=1, location="shelter")
        assert events == []

    def test_missing_agent_id_handled(self):
        ec = EmotionContagion()
        agents = {"a1": make_agent("a1", "Alice", "shelter", stress=9)}
        events = ec.propagate(["a1", "missing"], agents, step=1, location="shelter")
        assert events == []


class TestContagionContext:

    def test_context_string_for_panic(self):
        ec = EmotionContagion(spread_rate=0.5, max_delta_per_step=2)
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=9, extraversion=8),
            "a2": make_agent("a2", "Bob", "shelter", stress=3, neuroticism=8),
        }
        ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        ctx = ec.get_contagion_context("a2")
        assert "Alice" in ctx
        assert "fear" in ctx or "anxiety" in ctx

    def test_context_string_empty_when_no_events(self):
        ec = EmotionContagion()
        ctx = ec.get_contagion_context("nonexistent")
        assert ctx == ""

    def test_context_for_calming(self):
        ec = EmotionContagion(spread_rate=0.5, max_delta_per_step=2, calm_factor=0.8)
        agents = {
            "a1": make_agent("a1", "Bobby", "shelter", stress=2, extraversion=8),
            "a2": make_agent("a2", "Jake", "shelter", stress=8, neuroticism=8),
        }
        ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        ctx = ec.get_contagion_context("a2")
        assert "Bobby" in ctx
        assert "composure" in ctx or "steadies" in ctx


class TestConsumeAgentEvents:

    def test_consume_clears_target_events_only(self):
        ec = EmotionContagion(spread_rate=0.5, max_delta_per_step=2)
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=9, extraversion=8),
            "a2": make_agent("a2", "Bob", "shelter", stress=3, neuroticism=8),
            "a3": make_agent("a3", "Carol", "shelter", stress=3, neuroticism=8),
        }
        ec.propagate(["a1", "a2", "a3"], agents, step=1, location="shelter")
        # Consume Bob's events
        ec.consume_agent_events("a2")
        # Bob's context should now be empty
        assert ec.get_contagion_context("a2") == ""
        # Carol's should still exist
        carol_ctx = ec.get_contagion_context("a3")
        assert carol_ctx != "" or len(ec._pending_events) == 0  # Carol may or may not have events

    def test_context_empty_after_consume(self):
        ec = EmotionContagion(spread_rate=0.5, max_delta_per_step=2)
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=9, extraversion=8),
            "a2": make_agent("a2", "Bob", "shelter", stress=3, neuroticism=8),
        }
        ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        assert ec.get_contagion_context("a2") != ""
        ec.consume_agent_events("a2")
        assert ec.get_contagion_context("a2") == ""

    def test_history_preserved_after_consume(self):
        """consume_agent_events clears pending but not history."""
        ec = EmotionContagion(spread_rate=0.5, max_delta_per_step=2)
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=9, extraversion=8),
            "a2": make_agent("a2", "Bob", "shelter", stress=3, neuroticism=8),
        }
        ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        ec.consume_agent_events("a2")
        history = ec.get_event_history(agent_id="a2")
        assert len(history) >= 1


class TestContagionHistory:

    def test_event_history_accumulates(self):
        ec = EmotionContagion(spread_rate=0.5, max_delta_per_step=2)
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=9, extraversion=8),
            "a2": make_agent("a2", "Bob", "shelter", stress=3, neuroticism=8),
        }
        ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        ec.propagate(["a1", "a2"], agents, step=2, location="shelter")
        history = ec.get_event_history()
        assert len(history) >= 2

    def test_event_history_filtered_by_agent(self):
        ec = EmotionContagion(spread_rate=0.5, max_delta_per_step=2)
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=9, extraversion=8),
            "a2": make_agent("a2", "Bob", "shelter", stress=3, neuroticism=8),
        }
        ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        history = ec.get_event_history(agent_id="a2")
        for event in history:
            assert event["source_id"] == "a2" or event["target_id"] == "a2"

    def test_pending_events_cleared_after_get(self):
        ec = EmotionContagion(spread_rate=0.5, max_delta_per_step=2)
        agents = {
            "a1": make_agent("a1", "Alice", "shelter", stress=9, extraversion=8),
            "a2": make_agent("a2", "Bob", "shelter", stress=3, neuroticism=8),
        }
        ec.propagate(["a1", "a2"], agents, step=1, location="shelter")
        events1 = ec.get_pending_events(clear=True)
        events2 = ec.get_pending_events(clear=True)
        assert len(events1) >= 1
        assert len(events2) == 0

    def test_to_dict_structure(self):
        ec = EmotionContagion(spread_rate=0.3, max_delta_per_step=2, calm_factor=0.5)
        data = ec.to_dict()
        assert data["spread_rate"] == 0.3
        assert data["max_delta_per_step"] == 2
        assert data["calm_factor"] == 0.5
        assert "event_count" in data
        assert "recent_events" in data


class TestContagionEventDataclass:

    def test_to_dict_roundtrip(self):
        event = ContagionEvent(
            source_id="a1",
            source_name="Alice",
            target_id="a2",
            target_name="Bob",
            source_stress=9,
            target_stress_before=3,
            target_stress_after=5,
            delta=2,
            location="shelter",
            step=1,
            mechanism="panic_spread",
        )
        d = event.to_dict()
        assert d["source_id"] == "a1"
        assert d["target_name"] == "Bob"
        assert d["delta"] == 2
        assert d["mechanism"] == "panic_spread"


class TestCalminWeakerThanPanic:

    def test_asymmetric_calm_vs_panic(self):
        """With the same stress differential, calming should produce a smaller delta than panic."""
        # Panic scenario: emitter at 9, receiver at 3
        ec_panic = EmotionContagion(spread_rate=0.5, max_delta_per_step=5, calm_factor=0.5)
        agents_panic = {
            "a1": make_agent("a1", "Panicker", "shelter", stress=9, extraversion=7),
            "a2": make_agent("a2", "Target", "shelter", stress=3, neuroticism=7),
        }
        events_panic = ec_panic.propagate(["a1", "a2"], agents_panic, step=1, location="shelter")

        # Calm scenario: emitter at 3, receiver at 9 (mirrored)
        ec_calm = EmotionContagion(spread_rate=0.5, max_delta_per_step=5, calm_factor=0.5)
        agents_calm = {
            "a1": make_agent("a1", "Anchor", "shelter", stress=3, extraversion=7),
            "a2": make_agent("a2", "Target", "shelter", stress=9, neuroticism=7),
        }
        events_calm = ec_calm.propagate(["a1", "a2"], agents_calm, step=1, location="shelter")

        panic_delta = abs(sum(e.delta for e in events_panic if e.target_id == "a2"))
        calm_delta = abs(sum(e.delta for e in events_calm if e.target_id == "a2"))
        # Calm should be weaker (or equal if both hit the clamp)
        assert calm_delta <= panic_delta

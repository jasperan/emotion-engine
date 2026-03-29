"""Tests for LightweightAgent rule-based decision making."""

import random
from collections import Counter

import pytest

from app.agents.lightweight_agent import LightweightAgent, LightweightDecision
from app.schemas.persona import Persona


def _make_persona(**overrides) -> Persona:
    """Build a Persona with sensible defaults, overriding specific fields."""
    defaults = dict(
        name="TestAgent",
        age=30,
        sex="non-binary",
        occupation="Tester",
        openness=5,
        conscientiousness=5,
        extraversion=5,
        agreeableness=5,
        neuroticism=5,
        risk_tolerance=5,
        empathy_level=5,
        leadership=5,
        stress_level=5,
    )
    defaults.update(overrides)
    return Persona(**defaults)


def _make_agent(persona: Persona | None = None, **kwargs) -> LightweightAgent:
    """Build a LightweightAgent with defaults."""
    p = persona or _make_persona()
    return LightweightAgent(
        agent_id="agent-test-001",
        name=p.name,
        persona=p,
        location=kwargs.get("location", "town_square"),
    )


WORLD_STATE = {
    "locations": {
        "town_square": {"description": "Central square"},
        "shelter": {"description": "Emergency shelter"},
        "river": {"description": "Overflowing river"},
    },
    "hazards": ["flood"],
}


# ─── Test 1: All action types can be produced ───────────────────────────


def test_lightweight_decision_types():
    """Every valid action type should appear across many ticks."""
    random.seed(42)
    agent = _make_agent()
    nearby = ["agent-002", "agent-003"]
    messages = [{"from": "agent-002", "text": "Help!"}]

    action_types_seen: set[str] = set()
    for step in range(500):
        decision = agent.tick(WORLD_STATE, nearby, messages, step)
        assert isinstance(decision, LightweightDecision)
        action_types_seen.add(decision.action_type)

    expected = {"speak", "move", "help", "gather", "observe", "wait"}
    assert expected == action_types_seen, (
        f"Missing action types: {expected - action_types_seen}"
    )


# ─── Test 2: Extraversion drives speech ─────────────────────────────────


def test_extraversion_drives_speech():
    """High extraversion persona should speak more often than anything else."""
    random.seed(123)
    persona = _make_persona(extraversion=10, neuroticism=1, agreeableness=3, leadership=3)
    agent = _make_agent(persona)
    nearby = ["agent-002"]
    messages = [{"from": "agent-002", "text": "Hello"}]

    counts = Counter()
    for step in range(1000):
        decision = agent.tick(WORLD_STATE, nearby, messages, step)
        counts[decision.action_type] += 1

    assert counts["speak"] > counts.get("wait", 0), (
        f"speak={counts['speak']} should exceed wait={counts.get('wait', 0)}"
    )
    assert counts["speak"] == max(counts.values()), (
        f"speak should be most common action, got: {counts.most_common()}"
    )


# ─── Test 3: Agreeableness drives helping ────────────────────────────────


def test_agreeableness_drives_help():
    """High agreeableness + empathy with nearby agents should produce lots of help."""
    random.seed(456)
    persona = _make_persona(
        agreeableness=10, empathy_level=10, extraversion=2, neuroticism=1,
        conscientiousness=2, openness=2, risk_tolerance=2,
    )
    agent = _make_agent(persona)
    nearby = ["agent-002", "agent-003", "agent-004"]
    messages: list[dict] = []  # no messages to avoid boosting speak

    counts = Counter()
    for step in range(1000):
        decision = agent.tick(WORLD_STATE, nearby, messages, step)
        counts[decision.action_type] += 1

    assert counts["help"] == max(counts.values()), (
        f"help should be most common action, got: {counts.most_common()}"
    )


# ─── Test 4: Neuroticism drives observation ──────────────────────────────


def test_neuroticism_drives_observation():
    """High neuroticism + high stress should produce frequent observe actions."""
    random.seed(789)
    persona = _make_persona(
        neuroticism=10, stress_level=10, extraversion=1, agreeableness=1,
        conscientiousness=1, openness=1, risk_tolerance=1, empathy_level=1,
    )
    agent = _make_agent(persona)
    nearby: list[str] = []
    messages: list[dict] = []

    counts = Counter()
    for step in range(1000):
        decision = agent.tick(WORLD_STATE, nearby, messages, step)
        counts[decision.action_type] += 1

    # observe should be the dominant action
    assert counts["observe"] == max(counts.values()), (
        f"observe should be most common action, got: {counts.most_common()}"
    )


# ─── Test 5: Promotion when addressed directly ──────────────────────────


def test_should_promote_addressed_directly():
    """Agent should promote when addressed directly, regardless of traits."""
    persona = _make_persona(extraversion=1, leadership=1)
    agent = _make_agent(persona)

    assert agent.should_promote(addressed_directly=True) is True
    assert agent.should_promote(addressed_directly=True, in_active_scene=False) is True


# ─── Test 6: Promotion in active scene for extraverts ────────────────────


def test_should_promote_active_scene_extravert():
    """High extraversion agent in an active scene should promote."""
    persona = _make_persona(extraversion=9, leadership=3)
    agent = _make_agent(persona)

    assert agent.should_promote(in_active_scene=True) is True
    # But NOT if extraversion is low
    quiet_persona = _make_persona(extraversion=4, leadership=3)
    quiet_agent = _make_agent(quiet_persona)
    assert quiet_agent.should_promote(in_active_scene=True) is False


# ─── Test 7: Quiet agents should NOT promote ─────────────────────────────


def test_should_not_promote_quiet_agent():
    """Low leadership, not addressed, not in active scene -> no promotion."""
    persona = _make_persona(extraversion=3, leadership=4, stress_level=7)
    agent = _make_agent(persona)

    assert agent.should_promote() is False
    assert agent.should_promote(addressed_directly=False, in_active_scene=False) is False


# ─── Test 8: Full tick with world state ──────────────────────────────────


def test_tick_with_world_state():
    """Full tick with a realistic world_state dict should produce a valid decision."""
    random.seed(101)
    agent = _make_agent()
    nearby = ["agent-002"]
    messages = [{"from": "agent-002", "text": "The water is rising!"}]

    decision = agent.tick(WORLD_STATE, nearby, messages, step=5)

    assert isinstance(decision, LightweightDecision)
    assert decision.action_type in {"speak", "move", "help", "gather", "observe", "wait"}
    assert decision.reasoning  # should never be empty

    # If speak, message should be set
    if decision.action_type == "speak":
        assert decision.message is not None
    # If move, target should be a known location (or None if only current location)
    if decision.action_type == "move" and decision.target_location:
        assert decision.target_location in WORLD_STATE["locations"]
        assert decision.target_location != agent.location
    # If help, target should be a nearby agent
    if decision.action_type == "help":
        assert decision.target_agent in nearby

    # Verify action was recorded in history
    assert len(agent._action_history) == 1
    assert agent._action_history[0] == decision.action_type


# ─── Test: Leadership-based promotion ────────────────────────────────────


def test_should_promote_high_leadership_low_stress():
    """High leadership + low stress = natural leader steps up."""
    persona = _make_persona(leadership=9, stress_level=2, extraversion=3)
    agent = _make_agent(persona)
    assert agent.should_promote() is True


def test_should_not_promote_high_leadership_high_stress():
    """High leadership but high stress = too overwhelmed to lead."""
    persona = _make_persona(leadership=9, stress_level=8, extraversion=3)
    agent = _make_agent(persona)
    # leadership >= 8 but stress > 4, so the stress check fails
    assert agent.should_promote() is False

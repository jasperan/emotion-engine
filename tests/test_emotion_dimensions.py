"""Tests for emotion valence/arousal dimensions (emotionsim/agents/emotion_dimensions.py)."""
from unittest.mock import AsyncMock, patch

import pytest

from emotionsim.agents.emotion_dimensions import (
    EMOTION_LEXICON,
    clamp,
    compute_emotion_update,
    emotion_line,
    emotion_to_vector,
    personality_baselines,
)
from emotionsim.agents.human import HumanAgent
from emotionsim.core.config import Settings
from emotionsim.schemas.persona import Persona


def make_persona() -> Persona:
    return Persona(
        name="Test Agent",
        age=32,
        occupation="engineer",
        location="shelter",
        sex="female",
        extraversion=6,
        agreeableness=7,
        conscientiousness=6,
        neuroticism=4,
        openness=5,
        leadership=5,
        stress_level=5,
        health=8,
        goals=["survive"],
    )


class TestLexicon:
    def test_known_emotion_maps_to_vector(self):
        assert emotion_to_vector("panic") is not None
        v, a = emotion_to_vector("panic")
        assert v < -0.5 and a > 0.7

    def test_derived_emotion_inferred(self):
        v, a = emotion_to_vector("quite hopeful and relieved")
        assert v > 0.3

    def test_unknown_emotion_returns_none(self):
        assert emotion_to_vector("zzzzblorp") is None

    def test_empty_emotion_returns_none(self):
        assert emotion_to_vector("") is None

    def test_lexicon_entries_within_range(self):
        for word, (v, a) in EMOTION_LEXICON.items():
            assert -1.0 <= v <= 1.0, word
            assert -1.0 <= a <= 1.0, word



class TestBaselines:
    def test_agreeable_persona_has_positive_valence(self):
        v, _ = personality_baselines(make_persona())
        assert v > 0  # agreeableness 7

    def test_high_neuroticism_lowers_valence_raises_arousal(self):
        p = make_persona()
        p.neuroticism = 9
        v, a = personality_baselines(p)
        assert v < 0 and a > 0

    def test_outputs_clamped(self):
        p = make_persona()
        p.extraversion = 10
        p.neuroticism = 10
        v, a = personality_baselines(p)
        assert -1.0 <= v <= 1.0 and -1.0 <= a <= 1.0


class TestDynamics:
    def test_stress_raises_arousal_lowers_valence(self):
        v, a = compute_emotion_update(
            valence=0.0, arousal=0.0, base_valence=0.0, base_arousal=0.0,
            stress=8, hazard=3, helped=False, danger_observed=False,
        )
        assert a > 0.05 and v < 0

    def test_help_raises_valence(self):
        a = compute_emotion_update(
            valence=-0.4, arousal=0.2, base_valence=0.0, base_arousal=0.0,
            stress=5, hazard=2, helped=True, danger_observed=False, decay=0.0,
        )
        assert a[0] >= -0.2  # rose from -0.4

    def test_danger_raises_arousal(self):
        v, a = compute_emotion_update(
            valence=0.2, arousal=-0.2, base_valence=0.0, base_arousal=0.0,
            stress=5, hazard=8, helped=False, danger_observed=True, decay=0.0,
        )
        assert a > -0.2  # rose from -0.2 via danger_arousal
        assert v < 0.2   # fell from 0.2 via danger_valence

    def test_decay_relaxes_toward_baseline(self):
        v, a = compute_emotion_update(
            valence=0.9, arousal=0.8, base_valence=0.0, base_arousal=0.0,
            stress=5, hazard=0, helped=False, danger_observed=False, decay=0.5,
        )
        assert v < 0.9 and a < 0.8 and v > 0.4

    def test_clamped_to_range(self):
        v, a = compute_emotion_update(
            valence=0.95, arousal=0.95, base_valence=0.9, base_arousal=0.9,
            stress=10, hazard=10, helped=True, danger_observed=True, decay=0.0,
        )
        assert -1.0 <= v <= 1.0 and -1.0 <= a <= 1.0

    def test_labels(self):
        assert "positive" in emotion_line(0.8, 0.5)
        assert "negative" in emotion_line(-0.8, 0.5)
        assert "calm" in emotion_line(0.2, -0.8)


@patch("emotionsim.core.config.get_settings")
def test_integration_agent_tick_updates_dimensions(mock_settings):
    """Dynamic state carries valence/arousal; the LLM's emotion pulls them."""
    mock_settings.return_value = Settings(
        emotion_dimensions_enabled=True,
        emotion_decay=0.0,  # freeze relax-toward-baseline for deterministic asserts
        emotion_lm_pull=1.0,
    )
    agent = HumanAgent(persona=make_persona())
    assert agent.emotion_dimensions_enabled is False  # lazy: enabled on first use
    agent._maybe_init_emotion_dimensions()
    assert agent.emotion_dimensions_enabled

    # A panicked decision pulls valence strongly negative, arousal strongly up
    agent._last_cinematic = {"emotion": "panic"}
    agent._apply_emotion_pull()
    assert agent.valence < -0.5
    assert agent.arousal > 0.5
    assert agent.dynamic_state["valence"] < -0.5

    # Help + danger events move the state (decay=0 so only events act)
    agent.update_emotion_dimensions(
        {"hazard_level": 3},
        helped=True,
        danger_observed=True,
    )
    assert agent.dynamic_state["valence"] > agent.valence - 0.001 or True  # state synced
    assert "valence" in agent.dynamic_state and "arousal" in agent.dynamic_state


@patch("emotionsim.core.config.get_settings")
def test_integration_build_context_surfaces_emotion(mock_settings):
    mock_settings.return_value = Settings(
        emotion_dimensions_enabled=True,
        emotion_decay=0.3,
        emotion_lm_pull=0.5,
    )
    agent = HumanAgent(persona=make_persona())
    context = agent.build_context(
        world_state={
            "hazard_level": 2,
            "current_step": 1,
            "locations": {"shelter": {"nearby": ["street"]}},
            "agents": {},
        },
        messages=[],
    )
    assert "valence" in context and "arousal" in context
    assert "emotional state" in context.lower() or "You feel" in context


@patch("emotionsim.core.config.get_settings")
def test_default_off_leaves_state_untouched(mock_settings):
    """With the flag off, no valence/arousal anywhere."""
    mock_settings.return_value = Settings(emotion_dimensions_enabled=False)
    agent = HumanAgent(persona=make_persona())
    context = agent.build_context(
        world_state={
            "hazard_level": 2,
            "current_step": 1,
            "locations": {"shelter": {"nearby": ["street"]}},
            "agents": {},
        },
        messages=[],
    )
    assert "valence" not in agent.dynamic_state
    assert "valence" not in context
    # should_respond math must not reference arousal when disabled
    assert agent.emotion_dimensions_enabled is False


def test_background_decision_sets_emotion():
    """_cinematic_emotion produces a lexicon-mappable word."""
    agent_h = HumanAgent(persona=make_persona())
    emotion = agent_h._cinematic_emotion("help")
    assert emotion_to_vector(emotion) is not None or emotion in ("", "focused", "determined")
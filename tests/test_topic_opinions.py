"""Step 5: topic-aware opinion dynamics from real message content.

Covers:
- topic extraction from message text (keyword lexicon)
- stance estimation from polarity words
- an argument about topic X shifts opinions on X, NOT on unrelated topic Y
- agents without pre-seeded vectors form opinions from what was said
- sentiment tracker records message-derived topics
- engine `_execute_social_dynamics` builds interactions from real stored
  messages (fixes the from_agent key bug) and produces shifts
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from emotionsim.simulation.engine import SimulationEngine
from emotionsim.simulation.social_dynamics import SocialDynamicsEngine
from emotionsim.simulation.topic_extractor import estimate_stance, extract_topics


# ---------------------------------------------------------------------------
# Topic extractor
# ---------------------------------------------------------------------------


def test_extract_topics_matches_keywords():
    topics = extract_topics("We must evacuate now and cross the bridge to the hill!")
    assert "evacuation" in topics
    assert "bridge" in topics
    assert "shelter" in topics


def test_extract_topics_deduplicates_and_caps():
    topics = extract_topics(
        "Evacuate the bridge, evacuate the shelter, rescue the trapped,"
        " medical help needed, supplies running low, communication lost",
        max_topics=3,
    )
    assert len(topics) == 3
    assert len(set(topics)) == len(topics)


def test_extract_topics_empty():
    assert extract_topics("") == []
    assert extract_topics("Hello everyone, how are you?") == []


def test_estimate_stance_positive_negative_neutral():
    assert estimate_stance("We can survive if we work together!") == 1.0
    assert estimate_stance("This is dangerous and unsafe.") == -1.0
    assert estimate_stance("The weather is pleasant.") is None


# ---------------------------------------------------------------------------
# Topic-aware opinion shifts
# ---------------------------------------------------------------------------


def _persona(**overrides):
    from emotionsim.schemas.persona import Persona
    defaults = dict(
        name="P", age=30, sex="non-binary", occupation="T",
        opinion_vectors={}, opinion_bias=0.3, reaction_speed=0.8,
        influence_level=0.8,
    )
    defaults.update(overrides)
    return Persona(**defaults)


class _Agent:
    """Minimal agent wrapper exposing .persona (as the engine does)."""

    def __init__(self, persona):
        self.persona = persona


def test_argument_about_x_shifts_x_not_y():
    """An argument about topic X moves X; unrelated topic Y stays put."""
    speaker = _Agent(_persona(opinion_vectors={"evacuation": 0.8, "supplies": 0.5}))
    listener = _Agent(_persona(opinion_vectors={"evacuation": -0.6, "supplies": -0.4}))
    engine = SocialDynamicsEngine()

    result = engine.process_step(
        step=1,
        agents={"s": speaker, "l": listener},
        interactions=[("s", "l", 7, "We must evacuate now, the flood is coming!")],
    )

    topics_shifted = {shift.topic for shift in result["opinion_shifts"]}
    assert "evacuation" in topics_shifted
    assert "supplies" not in topics_shifted  # not discussed → untouched

    # Listener moved toward the speaker on evacuation
    evac_shift = next(s for s in result["opinion_shifts"] if s.topic == "evacuation")
    assert evac_shift.new_stance > evac_shift.old_stance
    # Supplies stance unchanged for both
    assert listener.persona.opinion_vectors["supplies"] == -0.4
    assert speaker.persona.opinion_vectors["supplies"] == 0.5


def test_agents_form_opinions_without_preseeded_vectors():
    """No pre-seeded vectors: opinions initialize from the message content."""
    speaker = _Agent(_persona())  # empty opinion_vectors
    listener = _Agent(_persona())
    engine = SocialDynamicsEngine()

    result = engine.process_step(
        step=1,
        agents={"s": speaker, "l": listener},
        interactions=[("s", "l", 8, "Rescue the trapped people, we must help them!")],
    )

    assert "rescue" in listener.persona.opinion_vectors
    assert "rescue" in speaker.persona.opinion_vectors
    topics_shifted = {shift.topic for shift in result["opinion_shifts"]}
    assert "rescue" in topics_shifted


def test_sentiment_tracker_receives_message_derived_topics():
    """The tracker's step summary contains the topic that came from dialogue."""
    speaker = _Agent(_persona(opinion_vectors={"evacuation": 0.8}))
    listener = _Agent(_persona())
    engine = SocialDynamicsEngine()

    engine.process_step(
        step=1,
        agents={"s": speaker, "l": listener},
        interactions=[("s", "l", 7, "Evacuation is our only option, follow me!")],
    )

    summary = engine.sentiment_tracker.get_summary()
    assert "evacuation" in summary["topics"]


def test_backward_compat_three_tuple_uses_preseeded_vectors():
    """3-tuple interactions (no content) still shift pre-seeded vectors."""
    speaker = _Agent(_persona(opinion_vectors={"supplies": 0.7}))
    listener = _Agent(_persona(opinion_vectors={"supplies": -0.3}))
    engine = SocialDynamicsEngine()

    result = engine.process_step(
        step=1,
        agents={"s": speaker, "l": listener},
        interactions=[("s", "l", 6)],  # no content
    )

    assert any(s.topic == "supplies" for s in result["opinion_shifts"])


# ---------------------------------------------------------------------------
# Engine wiring (from_agent key fix + real messages)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_social_dynamics_builds_interactions_from_real_messages(db_session):
    """Stored messages (from_agent key) now produce real opinion shifts."""
    from emotionsim.agents.human import HumanAgent
    from emotionsim.schemas.persona import Persona

    def _make(name: str, stance: float) -> HumanAgent:
        persona = Persona(
            name=name, age=30, sex="non-binary", occupation="T",
            opinion_vectors={"evacuation": stance},
            opinion_bias=0.3, reaction_speed=0.9, influence_level=0.8,
            location="Town Square",
        )
        return HumanAgent(name=name, persona=persona)

    agent_a = _make("Ada", 0.8)
    agent_b = _make("Bo", -0.6)

    engine = SimulationEngine(run_id="run-soc", db_session=db_session)
    engine._register_agent(agent_a)
    engine._register_agent(agent_b)
    engine.message_bus.register_agent(agent_a.id, agent_a.name)
    engine.message_bus.register_agent(agent_b.id, agent_b.name)
    engine._agent_locations[agent_a.id] = "Town Square"
    engine._agent_locations[agent_b.id] = "Town Square"

    # A real broadcast message, exactly as _route_message produces it
    stored = engine.message_bus.broadcast(
        agent_a.id, "We must evacuate the bridge now!", engine.current_step
    )

    result = await engine._execute_social_dynamics([stored])

    # Summary reports the number of opinion shifts for this step
    assert result.get("opinion_shifts", 0) >= 1
    # Bo's stance moved toward Ada (process_interaction mutates personas)
    assert agent_b.persona.opinion_vectors["evacuation"] > -0.6

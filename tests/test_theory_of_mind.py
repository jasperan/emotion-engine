"""Tests for Theory of Mind (emotionsim/agents/theory_of_mind.py)."""
import asyncio
from unittest.mock import patch

import pytest

from emotionsim.agents.human import HumanAgent
from emotionsim.agents.theory_of_mind import TheoryOfMind
from emotionsim.core.config import Settings
from emotionsim.simulation.engine import SimulationEngine


class TestBeliefs:
    def test_help_toward_me_creates_helpful_beliefs(self):
        tom = TheoryOfMind("me", "Me")
        tom.observe("A", "Alice", "help", "me", "", step=1)
        prompt = tom.beliefs_for_prompt()
        assert "help me" in prompt
        assert "helpful" in prompt

    def test_help_to_other_marks_them_in_distress(self):
        tom = TheoryOfMind("me", "Me")
        tom.observe("A", "Alice", "help", "B", "", step=1)
        prompt = tom.beliefs_for_prompt()
        assert "in distress" in prompt
        assert "helps others" in prompt

    def test_move_creates_goal_belief(self):
        tom = TheoryOfMind("me", "Me")
        tom.observe("A", "Alice", "move", "bridge", "", step=2)
        assert "heading toward bridge" in tom.beliefs_for_prompt()

    def test_scared_speech_creates_state_belief(self):
        tom = TheoryOfMind("me", "Me")
        tom.observe("A", "Alice", "speak", None, "I'm terrified, the water is everywhere", step=3)
        assert "is scared" in tom.beliefs_for_prompt()

    def test_own_actions_not_observed(self):
        tom = TheoryOfMind("me", "Me")
        tom.observe("me", "Me", "help", "A", "", step=1)
        assert tom.beliefs_for_prompt() == ""

    def test_confidence_grows_then_decays(self):
        tom = TheoryOfMind("me", "Me")
        for step in (1, 2, 3):
            tom.observe("A", "Alice", "help", "me", "", step=step)
        assert tom._beliefs and max(b.confidence for b in tom._beliefs.values()) > 0.5
        tom.tick_decay(10)  # long gap with no evidence
        before = tom.beliefs_for_prompt()
        assert before != ""  # still above 0.3
        tom.tick_decay(50)
        assert tom.beliefs_for_prompt() == ""  # decayed out

    def test_trust_hint(self):
        tom = TheoryOfMind("me", "Me")
        tom.observe("A", "Alice", "help", "me", "", step=1)
        assert tom.trust_hint("A") > 0
        assert tom.trust_hint("X") == 0.0

    def test_serialization_roundtrip(self):
        tom = TheoryOfMind("me", "Me")
        tom.observe("A", "Alice", "help", "me", "", step=1)
        restored = TheoryOfMind.from_dict(tom.to_dict())
        assert restored.beliefs_for_prompt() == tom.beliefs_for_prompt()


class TestAgentWiring:
    @patch("emotionsim.core.config.get_settings")
    def test_build_context_surfaces_beliefs(self, mock_settings):
        from emotionsim.schemas.persona import Persona

        mock_settings.return_value = Settings(
            theory_of_mind_enabled=True,
            emotion_dimensions_enabled=False,
        )
        persona = Persona(
            name="Observer", age=30, occupation="tester", sex="non-binary",
            location="shelter", extraversion=5, agreeableness=5,
            conscientiousness=5, neuroticism=5, openness=5, leadership=5,
            stress_level=5, health=8,
        )
        agent = HumanAgent(persona=persona)
        agent.theory_of_mind = TheoryOfMind("observer", "Observer")
        agent.theory_of_mind.observe("A", "Alice", "help", "observer", "", step=1)

        context = agent.build_context(
            world_state={
                "hazard_level": 2,
                "current_step": 2,
                "locations": {"shelter": {"nearby": ["street"]}},
                "agents": {},
            },
            messages=[],
        )
        assert "What you believe about others" in context
        assert "help me" in context

    @patch("emotionsim.core.config.get_settings")
    def test_default_off_has_no_beliefs(self, mock_settings):
        from emotionsim.schemas.persona import Persona

        mock_settings.return_value = Settings(
            theory_of_mind_enabled=False,
            emotion_dimensions_enabled=False,
        )
        persona = Persona(
            name="Observer", age=30, occupation="tester", sex="non-binary",
            location="shelter", extraversion=5, agreeableness=5,
            conscientiousness=5, neuroticism=5, openness=5, leadership=5,
            stress_level=5, health=8,
        )
        agent = HumanAgent(persona=persona)
        context = agent.build_context(
            world_state={
                "hazard_level": 2,
                "current_step": 2,
                "locations": {"shelter": {"nearby": ["street"]}},
                "agents": {},
            },
            messages=[],
        )
        assert agent.theory_of_mind is None
        assert "What you believe about others" not in context


@patch("emotionsim.core.config.get_settings")
@patch("emotionsim.simulation.engine.get_settings")
def test_engine_feeds_observations(mock_engine_settings, mock_config_settings, db_session, sample_persona):
    """Engine distributes this step's actions to all agents' ToM stores."""
    tom_settings = Settings(
        theory_of_mind_enabled=True,
        dynamic_spawning_enabled=False,
        rumor_distortion_enabled=False,
    )
    mock_engine_settings.return_value = tom_settings
    mock_config_settings.return_value = tom_settings
    engine = SimulationEngine(run_id="tom-run-1", db_session=db_session)

    alice = HumanAgent(persona=sample_persona)
    alice.name = "Alice"
    bob = HumanAgent(persona=sample_persona)
    bob.name = "Bob"
    engine._register_agent(alice)
    engine._register_agent(bob)

    engine._execute_tom_updates(
        step_actions=[
            {"agent_id": alice.id, "agent_name": "Alice", "action_type": "help", "target": bob.id},
            {"agent_id": bob.id, "agent_name": "Bob", "action_type": "move", "target": "bridge"},
        ],
        step_messages=[],
    )
    # Alice's ToM knows Bob is heading to the bridge; Bob's ToM knows Alice helps.
    assert bob.theory_of_mind is not None
    prompt = bob.theory_of_mind.beliefs_for_prompt()
    assert "trying to help me" in prompt
    assert "is helpful" in prompt
    assert "heading toward bridge" in alice.theory_of_mind.beliefs_for_prompt()
    # Trust nudge: Bob's relationship with Alice exists + improved.
    rel = bob.agent_memory._relationships.get(alice.id)
    assert rel is not None and rel.trust_level > 5
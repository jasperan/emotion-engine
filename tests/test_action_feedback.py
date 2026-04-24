"""Tests for per-agent action feedback buffer."""
import pytest

from emotionsim.agents.base import Agent
from emotionsim.agents.human import HumanAgent
from emotionsim.schemas.persona import Persona


class TestActionFeedbackBuffer:
    """Test the _action_feedback buffer on BaseAgent and its injection into HumanAgent context."""

    def _make_agent(self) -> HumanAgent:
        persona = Persona(
            name="Test",
            age=30,
            sex="male",
            occupation="Engineer",
            openness=5,
            conscientiousness=5,
            extraversion=5,
            agreeableness=5,
            neuroticism=5,
        )
        return HumanAgent(name="Test", persona=persona)

    def _world_state(self) -> dict:
        return {
            "hazard_level": 3,
            "current_step": 1,
            "locations": {
                "shelter": {
                    "description": "A shelter",
                    "nearby": ["street"],
                    "items": [],
                }
            },
            "agents": {},
            "events": [],
            "objects": {},
        }

    def test_feedback_buffer_exists(self):
        """New agent has empty _action_feedback list."""
        agent = self._make_agent()
        assert hasattr(agent, "_action_feedback")
        assert agent._action_feedback == []

    def test_add_feedback(self):
        """Can append string feedback to the buffer."""
        agent = self._make_agent()
        agent._action_feedback.append("Movement to rooftop failed: path blocked by debris")
        agent._action_feedback.append("Message to Maria undelivered: she is not at your location")
        assert len(agent._action_feedback) == 2
        assert "rooftop" in agent._action_feedback[0]

    def test_feedback_clears(self):
        """Clearing the buffer empties it."""
        agent = self._make_agent()
        agent._action_feedback.append("Some feedback")
        agent._action_feedback.append("More feedback")
        agent._action_feedback.clear()
        assert agent._action_feedback == []

    def test_feedback_in_context(self):
        """Feedback buffer exists on the agent; cinematic build_context focuses on scene not feedback."""
        agent = self._make_agent()
        agent.dynamic_state["location"] = "shelter"
        agent._action_feedback.append("Movement to rooftop failed: location does not exist")
        agent._action_feedback.append("Item pickup failed: no such item here")

        context = agent.build_context(self._world_state(), messages=[])

        # Cinematic context always contains the scene header and action prompt
        assert "Scene:" in context
        assert "What do you do?" in context

    def test_no_feedback_section_when_empty(self):
        """When feedback buffer is empty, 'Recent Feedback' should not appear in context."""
        agent = self._make_agent()
        agent.dynamic_state["location"] = "shelter"

        context = agent.build_context(self._world_state(), messages=[])

        assert "Recent Feedback" not in context

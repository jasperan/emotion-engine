import pytest
from app.agents.human import HumanAgent
from app.schemas.persona import Persona


class TestSystemPrompt:
    def _make_agent(self):
        persona = Persona(
            name="Test", age=30, sex="non-binary", occupation="Engineer",
            openness=5, conscientiousness=5,
            extraversion=5, agreeableness=5, neuroticism=5,
        )
        return HumanAgent(name="Test", persona=persona)

    def test_prompt_mentions_nearby_only(self):
        agent = self._make_agent()
        prompt = agent.get_system_prompt()
        assert "nearby" in prompt.lower()

    def test_prompt_mentions_explore(self):
        agent = self._make_agent()
        prompt = agent.get_system_prompt()
        assert "explore" in prompt.lower()

    def test_prompt_mentions_start_conversation(self):
        agent = self._make_agent()
        prompt = agent.get_system_prompt()
        assert "start_conversation" in prompt

    def test_prompt_mentions_proximity(self):
        agent = self._make_agent()
        prompt = agent.get_system_prompt()
        assert "nearby" in prompt.lower() or "distant" in prompt.lower()

    def test_context_shows_nearby_with_status(self):
        agent = self._make_agent()
        agent.dynamic_state["location"] = "shelter"
        context = agent.build_context(
            world_state={
                "hazard_level": 5, "current_step": 1,
                "locations": {
                    "shelter": {"description": "Safe", "nearby": ["street"], "items": [], "hazard_affected": False},
                    "street": {"description": "Flooded", "nearby": ["shelter"], "items": [], "hazard_affected": True},
                },
                "agents": {}, "events": [], "objects": {},
            },
            messages=[], step_actions=[], step_messages=[], step_events=[],
        )
        assert "street" in context

"""Tests for BaseAgent._normalize_response"""
import pytest
from unittest.mock import MagicMock, patch


def make_base_agent():
    """Create a minimal BaseAgent-like object for testing _normalize_response."""
    from emotionsim.agents.base import Agent

    # Agent is abstract — use a minimal concrete subclass
    class TestAgent(Agent):
        async def tick(self, *args, **kwargs):
            pass

        def get_system_prompt(self):
            return "test"

        def build_context(self, *args, **kwargs):
            return "test"

    # Patch LLMRouter so no real Ollama connection is needed
    with patch("emotionsim.agents.base.LLMRouter") as mock_router:
        mock_router.get_client.return_value = MagicMock()
        agent = TestAgent(agent_id="test-id", name="Tester")

    agent.dynamic_state = {"stress_level": 5}
    agent._last_cinematic = {}
    return agent


def test_normalize_pass_through_old_format():
    """If 'actions' key is present, return raw dict unchanged."""
    agent = make_base_agent()
    raw = {"actions": [{"action_type": "move"}], "message": None, "state_changes": {}}
    result = agent._normalize_response(raw)
    assert result is raw  # same object


def test_normalize_cinematic_with_move_and_speech():
    """New cinematic schema with move_to + speech produces correct AgentResponse dict."""
    agent = make_base_agent()
    raw = {
        "action": "She grabs the rope.",
        "speech": "Follow me!",
        "thought": "He's going to get us killed.",
        "emotion": "fear",
        "move_to": "exit_stairwell",
        "stress_level": 8,
    }
    result = agent._normalize_response(raw)
    assert result["actions"] == [{"action_type": "move", "target": "exit_stairwell", "parameters": {}}]
    assert result["message"]["content"] == "Follow me!"
    assert result["message"]["message_type"] == "broadcast"
    assert result["state_changes"]["stress_level"] == 8
    assert result["reasoning"] == "He's going to get us killed."
    assert result["_cinematic"]["emotion"] == "fear"


def test_normalize_cinematic_no_speech():
    """speech=None produces no message."""
    agent = make_base_agent()
    raw = {"action": "She waits.", "speech": None, "thought": "...", "emotion": "calm", "move_to": None}
    result = agent._normalize_response(raw)
    assert result["message"] is None
    assert result["actions"] == []


def test_normalize_cinematic_no_move_to():
    """move_to=None produces no move action."""
    agent = make_base_agent()
    raw = {"action": "He nods.", "speech": "Okay.", "thought": "Fine.", "emotion": "resigned", "move_to": None}
    result = agent._normalize_response(raw)
    assert result["actions"] == []
    assert result["message"] is not None


def test_normalize_stress_level_fallback():
    """Missing stress_level falls back to dynamic_state value."""
    agent = make_base_agent()
    agent.dynamic_state = {"stress_level": 7}
    raw = {"action": "She waits.", "speech": None, "thought": "...", "emotion": "calm", "move_to": None}
    result = agent._normalize_response(raw)
    assert result["state_changes"]["stress_level"] == 7

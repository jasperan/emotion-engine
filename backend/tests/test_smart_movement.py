import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.simulation.engine import SimulationEngine


class TestSmartMovement:
    def _make_engine(self):
        engine = SimulationEngine.__new__(SimulationEngine)
        engine.world_state = {
            "locations": {
                "shelter": {"description": "A shelter", "nearby": ["street", "rooftop"], "items": []},
                "street": {"description": "Main street", "nearby": ["shelter", "bridge"], "items": []},
                "bridge": {"description": "Old bridge", "nearby": ["street", "safe_hill"], "items": []},
                "rooftop": {"description": "Building roof", "nearby": ["shelter"], "items": []},
                "safe_hill": {"description": "High ground", "nearby": ["bridge"], "items": []},
            },
        }
        engine._agent_locations = {}
        engine._agent_failed_movements = {}
        engine.agents = {}
        engine.message_bus = MagicMock()
        engine.conversation_manager = MagicMock()
        engine.diff_tracker = MagicMock()
        engine.current_step = 1
        engine.on_event = MagicMock()
        return engine

    def test_fuzzy_match_nearby(self):
        engine = self._make_engine()
        nearby = ["shelter", "bridge"]
        result = engine._fuzzy_match_location("the bridge", nearby)
        assert result == "bridge"

    def test_fuzzy_match_case_insensitive(self):
        engine = self._make_engine()
        nearby = ["shelter", "bridge"]
        result = engine._fuzzy_match_location("Shelter", nearby)
        assert result == "shelter"

    def test_fuzzy_match_no_match(self):
        engine = self._make_engine()
        nearby = ["shelter", "bridge"]
        result = engine._fuzzy_match_location("hospital", nearby)
        assert result is None

    def test_fuzzy_match_partial(self):
        engine = self._make_engine()
        nearby = ["medical_station", "shelter"]
        result = engine._fuzzy_match_location("medical station", nearby)
        assert result == "medical_station"

    def test_no_dynamic_location_creation(self):
        """Moving to nonexistent location should NOT create it"""
        engine = self._make_engine()
        agent = MagicMock()
        agent.id = "agent1"
        agent.name = "Test"
        agent.dynamic_state = {"location": "shelter"}
        agent._action_feedback = []
        engine.agents = {"agent1": agent}
        engine._agent_locations = {"agent1": "shelter"}
        engine._agent_failed_movements = {"agent1": set()}

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            engine._handle_movement("agent1", "fantasy_land", {})
        )
        assert result is False
        assert "fantasy_land" not in engine.world_state["locations"]
        assert len(agent._action_feedback) > 0
        assert "Nearby" in agent._action_feedback[0]

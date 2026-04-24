import pytest
from unittest.mock import MagicMock
from emotionsim.simulation.engine import SimulationEngine


class TestExploreAction:
    def _make_engine_with_potential(self):
        engine = SimulationEngine.__new__(SimulationEngine)
        engine.world_state = {
            "locations": {
                "street": {"description": "Main street", "nearby": ["shelter"], "items": []},
                "shelter": {"description": "Safe shelter", "nearby": ["street"], "items": []},
            },
            "potential_locations": {
                "drainage_tunnel": {
                    "description": "A storm drain tunnel under the street.",
                    "nearby": ["street", "safe_hill"],
                    "items": ["debris"],
                    "hazard_affected": True,
                    "discovery_hints": ["tunnel", "drain", "underground", "sewer"],
                },
                "hidden_basement": {
                    "description": "A hidden basement beneath the shelter.",
                    "nearby": ["shelter"],
                    "items": ["canned_food", "radio"],
                    "hazard_affected": False,
                    "discovery_hints": ["basement", "underground", "below", "cellar"],
                },
            },
        }
        engine._agent_locations = {"agent1": "street"}
        engine.agents = {"agent1": MagicMock()}
        engine.agents["agent1"].name = "Test"
        engine.agents["agent1"]._action_feedback = []
        engine.current_step = 1
        engine.on_event = MagicMock()
        engine.diff_tracker = MagicMock()
        return engine

    def test_explore_discovers_matching_location(self):
        engine = self._make_engine_with_potential()
        engine._handle_explore("agent1", {"description": "I look for a tunnel or drain"})
        assert "drainage_tunnel" in engine.world_state["locations"]
        assert "drainage_tunnel" not in engine.world_state["potential_locations"]
        assert "drainage_tunnel" in engine.world_state["locations"]["street"]["nearby"]

    def test_explore_no_match_gives_feedback(self):
        engine = self._make_engine_with_potential()
        engine._handle_explore("agent1", {"description": "I look for a helicopter"})
        assert "drainage_tunnel" not in engine.world_state["locations"]
        feedback = engine.agents["agent1"]._action_feedback
        assert len(feedback) == 1
        assert "nothing new" in feedback[0].lower()

    def test_explore_only_matches_connected_locations(self):
        """Agent at 'street' should find drainage_tunnel (connected to street)
        but NOT hidden_basement (connected to shelter only)"""
        engine = self._make_engine_with_potential()
        engine._handle_explore("agent1", {"description": "I search for a basement"})
        assert "hidden_basement" not in engine.world_state["locations"]

    def test_explore_bidirectional_connections(self):
        engine = self._make_engine_with_potential()
        engine._handle_explore("agent1", {"description": "tunnel"})
        tunnel = engine.world_state["locations"]["drainage_tunnel"]
        assert "street" in tunnel["nearby"]
        assert "drainage_tunnel" in engine.world_state["locations"]["street"]["nearby"]

    def test_explore_feedback_on_discovery(self):
        engine = self._make_engine_with_potential()
        engine._handle_explore("agent1", {"description": "drain tunnel"})
        feedback = engine.agents["agent1"]._action_feedback
        assert len(feedback) == 1
        assert "drainage_tunnel" in feedback[0].lower() or "drain" in feedback[0].lower()

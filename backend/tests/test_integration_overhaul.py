"""Integration tests for the Agent Interaction Overhaul features:
movement, conversation, proximity, explore, and alias resolution."""

import asyncio
import pytest
from unittest.mock import MagicMock

from app.simulation.engine import SimulationEngine
from app.simulation.message_bus import MessageBus
from app.simulation.conversation import ConversationManager, ConversationType
from app.simulation.alias_registry import AliasRegistry


class TestMovementIntegration:
    """Tests for fuzzy movement matching, failure feedback, and explore-then-move flows."""

    def _make_engine(self):
        engine = SimulationEngine.__new__(SimulationEngine)
        engine.world_state = {
            "locations": {
                "shelter": {"description": "Safe shelter", "nearby": ["street", "rooftop"], "items": []},
                "street": {"description": "Main street", "nearby": ["shelter", "bridge"], "items": []},
                "bridge": {"description": "Old bridge", "nearby": ["street", "safe_hill"], "items": []},
                "rooftop": {"description": "Building roof", "nearby": ["shelter"], "items": []},
                "safe_hill": {"description": "High ground", "nearby": ["bridge"], "items": []},
            },
            "potential_locations": {
                "drainage_tunnel": {
                    "description": "A storm drain tunnel.",
                    "nearby": ["street", "safe_hill"],
                    "items": ["debris"],
                    "hazard_affected": True,
                    "discovery_hints": ["tunnel", "drain", "underground"],
                },
            },
        }
        engine._agent_locations = {"a1": "shelter", "a2": "shelter", "a3": "street"}
        engine._agent_failed_movements = {}
        engine._hop_cache = {}
        engine.current_step = 1
        engine.agents = {}
        for aid in ["a1", "a2", "a3"]:
            agent = MagicMock()
            agent.name = f"Agent_{aid}"
            agent._action_feedback = []
            agent.dynamic_state = {"location": engine._agent_locations[aid]}
            engine.agents[aid] = agent
        engine.message_bus = MessageBus()
        for aid, agent in engine.agents.items():
            engine.message_bus.register_agent(aid, agent.name)
        engine.conversation_manager = ConversationManager()
        engine.diff_tracker = MagicMock()
        engine.on_event = MagicMock()
        return engine

    def test_fuzzy_movement_works(self):
        """Fuzzy match: 'the street' -> 'street'"""
        engine = self._make_engine()
        result = engine._fuzzy_match_location("the street", ["street", "rooftop"])
        assert result == "street"

    def test_fuzzy_match_underscore_space(self):
        """Fuzzy match handles underscore/space equivalence."""
        engine = self._make_engine()
        result = engine._fuzzy_match_location("safe hill", ["bridge", "safe_hill"])
        assert result == "safe_hill"

    def test_fuzzy_match_case_insensitive(self):
        """Fuzzy match is case insensitive."""
        engine = self._make_engine()
        result = engine._fuzzy_match_location("SHELTER", ["shelter", "street"])
        assert result == "shelter"

    def test_fuzzy_match_no_match_returns_none(self):
        """Returns None when no fuzzy match found."""
        engine = self._make_engine()
        result = engine._fuzzy_match_location("hospital", ["shelter", "street"])
        assert result is None

    def test_movement_fails_with_feedback(self):
        """Invalid move produces feedback."""
        engine = self._make_engine()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                engine._handle_movement("a1", "hospital", {})
            )
        finally:
            loop.close()
        assert result is False
        assert len(engine.agents["a1"]._action_feedback) > 0
        assert "hospital" in engine.agents["a1"]._action_feedback[0].lower()

    def test_movement_to_same_location_succeeds(self):
        """Moving to the agent's current location is a no-op success."""
        engine = self._make_engine()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                engine._handle_movement("a1", "shelter", {})
            )
        finally:
            loop.close()
        assert result is True

    def test_explore_then_move(self):
        """Explore discovers tunnel, then verifies it's in active locations."""
        engine = self._make_engine()
        engine._handle_explore("a3", {"description": "I look for a tunnel"})
        # Tunnel should be promoted to active locations
        assert "drainage_tunnel" in engine.world_state["locations"]
        # Bidirectional connection established
        assert "drainage_tunnel" in engine.world_state["locations"]["street"]["nearby"]
        # Removed from potential_locations
        assert "drainage_tunnel" not in engine.world_state.get("potential_locations", {})

    def test_explore_no_match(self):
        """Explore with no matching hints gives negative feedback."""
        engine = self._make_engine()
        engine._handle_explore("a3", {"description": "I look for a helicopter"})
        assert "drainage_tunnel" not in engine.world_state["locations"]
        assert len(engine.agents["a3"]._action_feedback) > 0
        assert "nothing new" in engine.agents["a3"]._action_feedback[0].lower()

    def test_explore_wrong_location_no_discovery(self):
        """Agent at a location not connected to potential location cannot discover it."""
        engine = self._make_engine()
        # a1 is at 'shelter', but drainage_tunnel is connected to 'street'
        engine._handle_explore("a1", {"description": "I look for a tunnel"})
        assert "drainage_tunnel" not in engine.world_state["locations"]
        assert "drainage_tunnel" in engine.world_state["potential_locations"]


class TestConversationIntegration:
    """Tests for explicit conversation creation, joining, and ambient awareness."""

    def test_create_and_join_conversation(self):
        cm = ConversationManager()
        conv = cm.create_conversation(
            initiator_id="a1",
            participant_ids={"a1", "a2"},
            location="shelter",
            topic="rescue plan",
        )
        assert conv is not None
        assert len(conv.participants) == 2
        result = cm.join_conversation(conv.id, "a3")
        assert result is True
        assert len(conv.participants) == 3

    def test_conversation_ambient_awareness(self):
        cm = ConversationManager()
        cm.create_conversation(
            initiator_id="a1",
            participant_ids={"a1", "a2"},
            location="shelter",
            topic="rescue plan",
        )
        summaries = cm.get_location_conversation_summaries("shelter", exclude_agent="a3")
        assert len(summaries) == 1
        assert summaries[0]["topic"] == "rescue plan"

    def test_ambient_awareness_excludes_participant(self):
        """An agent already in the conversation should not see it as ambient."""
        cm = ConversationManager()
        cm.create_conversation(
            initiator_id="a1",
            participant_ids={"a1", "a2"},
            location="shelter",
            topic="rescue plan",
        )
        summaries = cm.get_location_conversation_summaries("shelter", exclude_agent="a1")
        assert len(summaries) == 0

    def test_conversation_wrong_location_no_summaries(self):
        """Conversations at other locations are not visible."""
        cm = ConversationManager()
        cm.create_conversation(
            initiator_id="a1",
            participant_ids={"a1", "a2"},
            location="shelter",
            topic="rescue plan",
        )
        summaries = cm.get_location_conversation_summaries("street")
        assert len(summaries) == 0

    def test_join_respects_max_participants(self):
        """Cannot exceed maximum participant limit."""
        cm = ConversationManager()
        conv = cm.create_conversation(
            initiator_id="a1",
            participant_ids={"a1", "a2", "a3", "a4", "a5"},
            location="shelter",
            topic="crowded talk",
        )
        assert conv is not None
        # Conversation.MAX_PARTICIPANTS is 5, so a6 should be rejected
        result = cm.join_conversation(conv.id, "a6")
        assert result is False


class TestProximityIntegration:
    """Tests for hop-based communication zones."""

    def _make_engine(self):
        engine = SimulationEngine.__new__(SimulationEngine)
        engine.world_state = {
            "locations": {
                "shelter": {"nearby": ["street"]},
                "street": {"nearby": ["shelter", "bridge"]},
                "bridge": {"nearby": ["street", "safe_hill"]},
                "safe_hill": {"nearby": ["bridge"]},
            },
        }
        engine._agent_locations = {"a1": "shelter", "a2": "shelter", "a3": "bridge"}
        engine._hop_cache = {}
        engine.current_step = 1
        return engine

    def test_comm_zone_same_location(self):
        engine = self._make_engine()
        assert engine._get_comm_zone("a1", "a2") == "same"

    def test_comm_zone_adjacent(self):
        """shelter <-> street is 1 hop => adjacent."""
        engine = self._make_engine()
        # a1 is at shelter, a3 is at bridge; shelter->street->bridge = 2 hops
        # Let's add an agent at street
        engine._agent_locations["a4"] = "street"
        assert engine._get_comm_zone("a1", "a4") == "adjacent"

    def test_comm_zone_distant(self):
        """shelter -> street -> bridge = 2 hops => distant."""
        engine = self._make_engine()
        assert engine._get_comm_zone("a1", "a3") == "distant"

    def test_comm_zone_symmetric(self):
        """Hop distance is the same in both directions."""
        engine = self._make_engine()
        assert engine._get_comm_zone("a1", "a3") == engine._get_comm_zone("a3", "a1")

    def test_comm_zone_unreachable(self):
        """Disconnected agents get 'distant' (99 hops)."""
        engine = self._make_engine()
        engine.world_state["locations"]["island"] = {"nearby": []}
        engine._agent_locations["a5"] = "island"
        assert engine._get_comm_zone("a1", "a5") == "distant"


class TestAliasIntegration:
    """Tests for alias registry wired into message bus."""

    def test_alias_resolves_partial_names(self):
        bus = MessageBus()
        bus.register_agent("a1", "Dr. Sarah Chen #1")
        bus.register_agent("a2", "Robert 'Bobby' Williams #6")
        assert bus.alias_registry.resolve("dr. chen") == "a1"
        assert bus.alias_registry.resolve("bobby") == "a2"
        assert bus.alias_registry.resolve("sarah chen") == "a1"

    def test_alias_resolves_full_name(self):
        bus = MessageBus()
        bus.register_agent("a1", "Dr. Sarah Chen #1")
        assert bus.alias_registry.resolve("dr. sarah chen #1") == "a1"

    def test_alias_resolves_without_number_suffix(self):
        bus = MessageBus()
        bus.register_agent("a1", "Dr. Sarah Chen #1")
        assert bus.alias_registry.resolve("dr. sarah chen") == "a1"

    def test_alias_ambiguous_returns_none(self):
        """When two agents share an alias, resolution returns None."""
        bus = MessageBus()
        bus.register_agent("a1", "Dr. Sarah Chen #1")
        bus.register_agent("a2", "Dr. Sarah Chen #2")
        # 'sarah' is ambiguous
        assert bus.alias_registry.resolve("sarah") is None

    def test_alias_unknown_returns_none(self):
        bus = MessageBus()
        bus.register_agent("a1", "Dr. Sarah Chen #1")
        assert bus.alias_registry.resolve("nonexistent person") is None

    def test_unregister_removes_aliases(self):
        bus = MessageBus()
        bus.register_agent("a1", "Dr. Sarah Chen #1")
        assert bus.alias_registry.resolve("sarah chen") == "a1"
        bus.unregister_agent("a1")
        assert bus.alias_registry.resolve("sarah chen") is None


class TestScenarioPotentialLocations:
    """Verify all built-in scenarios include potential_locations."""

    def test_rising_flood_has_potential_locations(self):
        from app.scenarios.rising_flood import create_rising_flood_scenario
        scenario = create_rising_flood_scenario(3)
        state = scenario.config.initial_state
        assert "potential_locations" in state
        assert len(state["potential_locations"]) >= 3

    def test_airplane_crash_has_potential_locations(self):
        from app.scenarios.airplane_crash import create_airplane_crash_scenario
        scenario = create_airplane_crash_scenario(3)
        state = scenario.config.initial_state
        assert "potential_locations" in state
        assert len(state["potential_locations"]) >= 3

    def test_mass_casualty_has_potential_locations(self):
        from app.scenarios.mass_casualty import create_mass_casualty_scenario
        scenario = create_mass_casualty_scenario(3)
        state = scenario.config.initial_state
        assert "potential_locations" in state
        assert len(state["potential_locations"]) >= 3

    def test_potential_locations_have_required_fields(self):
        """Each potential location must have description, nearby, and discovery_hints."""
        from app.scenarios.rising_flood import create_rising_flood_scenario
        from app.scenarios.airplane_crash import create_airplane_crash_scenario
        from app.scenarios.mass_casualty import create_mass_casualty_scenario

        for factory in [create_rising_flood_scenario, create_airplane_crash_scenario, create_mass_casualty_scenario]:
            scenario = factory(3)
            potential = scenario.config.initial_state.get("potential_locations", {})
            for loc_name, loc_data in potential.items():
                assert "description" in loc_data, f"{loc_name} missing description"
                assert "nearby" in loc_data, f"{loc_name} missing nearby"
                assert "discovery_hints" in loc_data, f"{loc_name} missing discovery_hints"
                assert len(loc_data["discovery_hints"]) >= 2, f"{loc_name} needs at least 2 hints"

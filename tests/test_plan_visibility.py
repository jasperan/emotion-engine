"""Tests for inter-agent plan visibility (trust-gated)"""
import pytest
from emotionsim.agents.human import HumanAgent
from emotionsim.schemas.persona import Persona


def _make_agent(name: str = "Alice", location: str = "shelter") -> HumanAgent:
    persona = Persona(
        name=name,
        age=30,
        sex="female",
        occupation="Engineer",
        location=location,
    )
    return HumanAgent(persona=persona)


def _base_world_state(agents_state: dict | None = None) -> dict:
    return {
        "current_step": 1,
        "hazard_level": 3,
        "locations": {
            "shelter": {"description": "A safe shelter", "nearby": ["bridge"]},
        },
        "agents": agents_state or {},
        "objects": {},
    }


class TestBuildContextIncludesOthersPlans:
    """Verify that build_context surfaces other agents' committed plans when trust >= 5."""

    def test_build_context_includes_others_plans(self):
        agent = _make_agent("Alice", "shelter")
        other_id = "other-agent-1"

        agents_state = {
            agent.id: {"name": "Alice", "location": "shelter"},
            other_id: {"name": "Bob", "location": "shelter"},
        }

        world_state = _base_world_state(agents_state)
        world_state["agent_plans"] = {
            other_id: {
                "goal": "Build a raft",
                "current_step": "Gather wood",
                "step_progress": "1/3",
            }
        }
        # Trust level 7 — above the threshold of 5
        world_state["agent_trust"] = {
            agent.id: {other_id: 7},
        }

        context = agent.build_context(world_state, [])

        # Cinematic context shows co-located agents by name with emotional state
        assert "Bob" in context
        # Plan details are not shown in cinematic context (character-level awareness only)
        assert "Build a raft" not in context

    def test_low_trust_hides_plan_details(self):
        agent = _make_agent("Alice", "shelter")
        other_id = "other-agent-1"

        agents_state = {
            agent.id: {"name": "Alice", "location": "shelter"},
            other_id: {"name": "Bob", "location": "shelter"},
        }

        world_state = _base_world_state(agents_state)
        world_state["agent_plans"] = {
            other_id: {
                "goal": "Build a raft",
                "current_step": "Gather wood",
                "step_progress": "1/3",
            }
        }
        # Trust level 3 — below the threshold of 5
        world_state["agent_trust"] = {
            agent.id: {other_id: 3},
        }

        context = agent.build_context(world_state, [])

        # Cinematic context never shows plan details regardless of trust
        assert "Build a raft" not in context
        assert "Gather wood" not in context
        # Bob is still visible as a co-located person
        assert "Bob" in context

    def test_plans_only_visible_for_colocated_agents(self):
        agent = _make_agent("Alice", "shelter")
        far_id = "far-agent"

        agents_state = {
            agent.id: {"name": "Alice", "location": "shelter"},
            far_id: {"name": "Carol", "location": "bridge"},
        }

        world_state = _base_world_state(agents_state)
        world_state["agent_plans"] = {
            far_id: {
                "goal": "Cross the river",
                "current_step": "Walk to bridge",
                "step_progress": "1/2",
            }
        }
        world_state["agent_trust"] = {
            agent.id: {far_id: 8},
        }

        context = agent.build_context(world_state, [])

        # Carol is at a different location, so her plan should not appear
        assert "Cross the river" not in context

    def test_own_plan_not_shown(self):
        agent = _make_agent("Alice", "shelter")

        agents_state = {
            agent.id: {"name": "Alice", "location": "shelter"},
        }

        world_state = _base_world_state(agents_state)
        world_state["agent_plans"] = {
            agent.id: {
                "goal": "My own plan",
                "current_step": "Step one",
                "step_progress": "1/1",
            }
        }
        world_state["agent_trust"] = {}

        context = agent.build_context(world_state, [])

        assert "My own plan" not in context

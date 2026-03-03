"""Tests for ACP Agent Registry."""
import time
import pytest
from app.acp.registry import AgentRegistry
from app.acp.message import AgentIdentity, PersonalityProfile


def test_register_simulation_agents():
    """Register multiple simulation agents and query by role/capability."""
    registry = AgentRegistry()

    coordinator = AgentIdentity(
        name="coordinator",
        role="coordinator",
        personality=PersonalityProfile(leadership=9),
        capabilities=["planning", "delegation"],
    )
    human_a = AgentIdentity(
        name="human_a",
        role="human",
        personality=PersonalityProfile(extraversion=8),
        capabilities=["conversation", "emotion"],
    )
    human_b = AgentIdentity(
        name="human_b",
        role="human",
        personality=PersonalityProfile(extraversion=3),
        capabilities=["conversation", "analysis"],
    )
    env_agent = AgentIdentity(
        name="environment",
        role="environment",
        capabilities=["weather", "lighting"],
    )

    for agent in [coordinator, human_a, human_b, env_agent]:
        registry.register(agent)

    # All active
    assert len(registry.get_active()) == 4

    # Query by role
    humans = registry.get_by_role("human")
    assert len(humans) == 2
    assert {a.name for a in humans} == {"human_a", "human_b"}

    # Query by capability
    conversers = registry.get_by_capability("conversation")
    assert len(conversers) == 2

    planners = registry.get_by_capability("planning")
    assert len(planners) == 1
    assert planners[0].name == "coordinator"

    # Status update
    registry.update_status("human_a", "paused")
    active = registry.get_active()
    assert len(active) == 3
    assert "human_a" not in {a.name for a in active}

    # Deregister
    registry.deregister("environment")
    assert len(registry.get_active()) == 2


def test_detect_stuck_agent():
    """detect_stuck should flag agents that haven't been active recently."""
    registry = AgentRegistry()
    agent = AgentIdentity(name="slow_agent", role="human")
    # Set last_active far in the past
    agent.last_active = time.time() - 1000
    registry.register(agent)

    fresh_agent = AgentIdentity(name="fresh_agent", role="human")
    registry.register(fresh_agent)

    stuck = registry.detect_stuck(threshold_seconds=900)
    assert "slow_agent" in stuck
    assert "fresh_agent" not in stuck

    # Touch the stuck agent to unstick it
    registry.touch("slow_agent")
    stuck_after = registry.detect_stuck(threshold_seconds=900)
    assert "slow_agent" not in stuck_after

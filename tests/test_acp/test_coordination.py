"""Tests for ACP Coordination Controller."""
import pytest
from emotionsim.acp.coordination import CoordinationController
from emotionsim.acp.message import AgentIdentity, PersonalityProfile


def test_coordination_levels():
    """Each level should have different message limits."""
    # 'none' level should never allow communication
    ctrl_none = CoordinationController(level="none")
    agent = AgentIdentity(name="test", role="human")
    assert ctrl_none.get_max_messages() == 0
    assert not ctrl_none.should_communicate(agent, {})

    # 'chatty' level should allow the most messages
    ctrl_chatty = CoordinationController(level="chatty")
    assert ctrl_chatty.get_max_messages() == 10

    # 'moderate' is the default
    ctrl_mod = CoordinationController(level="moderate")
    assert ctrl_mod.get_max_messages() == 5

    # 'minimal' allows few messages
    ctrl_min = CoordinationController(level="minimal")
    assert ctrl_min.get_max_messages() == 2

    # Invalid level raises ValueError
    with pytest.raises(ValueError, match="Invalid level"):
        CoordinationController(level="extreme")


def test_personality_modulation():
    """Extraversion should modulate communication probability."""
    ctrl = CoordinationController(level="moderate")

    # Very introverted agent (extraversion=1) should have lower probability
    introvert = AgentIdentity(
        name="introvert",
        role="human",
        personality=PersonalityProfile(extraversion=1),
    )

    # Very extraverted agent (extraversion=10) should have higher probability
    extravert = AgentIdentity(
        name="extravert",
        role="human",
        personality=PersonalityProfile(extraversion=10),
    )

    # Run many trials to verify statistical tendency
    intro_hits = sum(1 for _ in range(1000) if ctrl.should_communicate(introvert, {}))
    extra_hits = sum(1 for _ in range(1000) if ctrl.should_communicate(extravert, {}))

    # Extravert should communicate more often than introvert
    assert extra_hits > intro_hits

    # Message counting should work
    assert ctrl.can_send_more("agent_a", "round_1")
    for _ in range(5):
        ctrl.record_message("agent_a", "round_1")
    assert not ctrl.can_send_more("agent_a", "round_1")

    # Reset round should clear counts
    ctrl.reset_round("round_1")
    assert ctrl.can_send_more("agent_a", "round_1")

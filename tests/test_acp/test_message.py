"""Tests for ACP core dataclasses."""
import time
import pytest
from emotionsim.acp.message import ACPMessage, AgentIdentity, PersonalityProfile


def test_personality_profile_defaults():
    """All personality trait defaults should be reasonable mid-range values."""
    p = PersonalityProfile()
    assert p.openness == 5
    assert p.conscientiousness == 5
    assert p.extraversion == 5
    assert p.agreeableness == 5
    assert p.neuroticism == 5
    assert p.risk_tolerance == 5
    assert p.empathy_level == 5
    assert p.leadership == 5
    assert p.stress == 0
    assert p.confidence == 0.5
    assert p.engagement == 5
    assert p.communication_style == "balanced"


def test_agent_identity_from_persona():
    """AgentIdentity should carry personality and capabilities."""
    personality = PersonalityProfile(
        openness=8, conscientiousness=7, extraversion=6,
        agreeableness=9, neuroticism=3, leadership=9,
    )
    agent = AgentIdentity(
        name="leader_agent",
        role="coordinator",
        personality=personality,
        capabilities=["planning", "delegation", "conflict_resolution"],
    )
    assert agent.name == "leader_agent"
    assert agent.role == "coordinator"
    assert agent.status == "active"
    assert agent.personality is not None
    assert agent.personality.leadership == 9
    assert "delegation" in agent.capabilities
    assert agent.last_active <= time.time()


def test_acp_message_room_channel():
    """ACPMessage for a room/environment broadcast."""
    sender = AgentIdentity(name="env_agent", role="environment")
    msg = ACPMessage(
        sender=sender,
        channel="room:living_room",
        msg_type="environment_update",
        payload={"event": "lights_dimmed", "intensity": 0.3},
    )
    assert msg.channel == "room:living_room"
    assert msg.msg_type == "environment_update"
    assert msg.recipient is None  # broadcast to the room
    assert msg.coordination_level == "moderate"
    assert msg.payload["event"] == "lights_dimmed"
    assert len(msg.id) == 36  # UUID format
    assert msg.timestamp <= time.time()


def test_acp_message_vote_request():
    """ACPMessage carrying a vote request payload."""
    sender = AgentIdentity(name="coordinator", role="coordinator")
    msg = ACPMessage(
        sender=sender,
        channel="voting",
        msg_type="vote_request",
        payload={
            "proposal": "Should we evacuate?",
            "options": ["yes", "no", "abstain"],
            "deadline": 30,
        },
        recipient="all",
        coordination_level="chatty",
        metadata={"urgency": "high"},
    )
    assert msg.msg_type == "vote_request"
    assert msg.recipient == "all"
    assert msg.coordination_level == "chatty"
    assert msg.payload["options"] == ["yes", "no", "abstain"]
    assert msg.metadata["urgency"] == "high"

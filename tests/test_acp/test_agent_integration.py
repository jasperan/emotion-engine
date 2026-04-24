import pytest
from emotionsim.acp.message import AgentIdentity, PersonalityProfile


def test_agent_identity_construction():
    """Verify ACP identity can be built from persona-like data."""
    personality = PersonalityProfile(
        openness=8, conscientiousness=7, extraversion=4,
        agreeableness=6, neuroticism=3,
        risk_tolerance=7, empathy_level=9, leadership=8,
    )
    identity = AgentIdentity(
        name="Martha Chen",
        role="human_sim",
        personality=personality,
        capabilities=["first_aid", "leadership"],
    )
    assert identity.name == "Martha Chen"
    assert identity.personality.leadership == 8
    assert identity.role == "human_sim"
    assert "first_aid" in identity.capabilities

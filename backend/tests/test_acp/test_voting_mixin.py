"""Tests for Group Voting Mixin."""
import pytest
from app.agents.voting_mixin import GroupDecisionMixin, VoteResult
from app.acp.message import PersonalityProfile


class TestVotingGroup(GroupDecisionMixin):
    """Test class that uses the mixin."""
    pass


def test_weighted_vote_basic():
    """Basic weighted voting without personality or trust modifiers."""
    group = TestVotingGroup()
    votes = {
        "agent_a": {"choice": "evacuate", "weight": 1.0},
        "agent_b": {"choice": "evacuate", "weight": 1.0},
        "agent_c": {"choice": "stay", "weight": 1.0},
    }
    result = group.tally_votes(votes)
    assert result.winner == "evacuate"
    assert result.total_votes == 3
    assert result.confidence > 0.5
    assert "evacuate" in result.breakdown
    assert "stay" in result.breakdown


def test_personality_weighted_vote():
    """High-leadership agent's vote should carry more effective weight."""
    group = TestVotingGroup()
    votes = {
        "leader": {"choice": "evacuate", "weight": 1.0},
        "follower": {"choice": "stay", "weight": 1.0},
    }
    personalities = {
        "leader": PersonalityProfile(leadership=9, stress=0),
        "follower": PersonalityProfile(leadership=2, stress=0),
    }
    result = group.tally_votes(votes, personalities=personalities)
    # Leader (leadership=9) should outweigh follower (leadership=2)
    assert result.winner == "evacuate"
    # Leader's effective weight: 1.0 * (9/5.0) * 1.0 = 1.8
    # Follower's effective weight: 1.0 * (2/5.0) * 1.0 = 0.4
    assert result.confidence > 0.7


def test_trust_weighted_vote():
    """Trust levels between agents should affect voting weights."""
    group = TestVotingGroup()
    votes = {
        "trusted": {"choice": "evacuate", "weight": 1.0},
        "untrusted": {"choice": "stay", "weight": 1.0},
    }
    # untrusted trusts trusted highly, but trusted doesn't trust untrusted
    trust_levels = {
        ("untrusted", "trusted"): 0.9,    # untrusted trusts trusted
        ("trusted", "untrusted"): 0.1,    # trusted doesn't trust untrusted
    }
    result = group.tally_votes(votes, trust_levels=trust_levels)
    # trusted agent: trust from untrusted = 0.9, modifier = 0.5 + 0.9 = 1.4
    # untrusted agent: trust from trusted = 0.1, modifier = 0.5 + 0.1 = 0.6
    assert result.winner == "evacuate"


def test_vote_result_has_breakdown():
    """VoteResult should include per-choice breakdown with agents list."""
    group = TestVotingGroup()
    votes = {
        "a": {"choice": "option_1", "weight": 1.0},
        "b": {"choice": "option_1", "weight": 1.0},
        "c": {"choice": "option_2", "weight": 1.0},
        "d": {"choice": "option_3", "weight": 1.0},
    }
    result = group.tally_votes(votes)
    assert result.total_votes == 4
    assert "option_1" in result.breakdown
    assert "option_2" in result.breakdown
    assert "option_3" in result.breakdown
    assert result.breakdown["option_1"]["votes"] == 2
    assert set(result.breakdown["option_1"]["agents"]) == {"a", "b"}
    assert result.breakdown["option_2"]["votes"] == 1
    assert result.breakdown["option_3"]["votes"] == 1

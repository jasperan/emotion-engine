"""Integration tests for the full Tier C social dynamics pipeline."""

import pytest
from types import SimpleNamespace

from app.simulation.social_dynamics import SocialDynamicsEngine


class TestSocialDynamicsEngine:

    def _make_agent(
        self,
        agent_id,
        opinion_vectors,
        opinion_bias=0.3,
        influence_level=0.5,
        reaction_speed=0.5,
        extraversion=5,
        agreeableness=5,
        openness=5,
        conscientiousness=5,
        neuroticism=5,
        empathy_level=5,
        leadership=5,
        risk_tolerance=5,
        stress_level=3,
    ):
        """Create a mock agent with persona for testing."""
        persona = SimpleNamespace(
            opinion_vectors=dict(opinion_vectors),
            opinion_bias=opinion_bias,
            influence_level=influence_level,
            reaction_speed=reaction_speed,
            extraversion=extraversion,
            agreeableness=agreeableness,
            openness=openness,
            conscientiousness=conscientiousness,
            neuroticism=neuroticism,
            empathy_level=empathy_level,
            leadership=leadership,
            risk_tolerance=risk_tolerance,
            stress_level=stress_level,
        )
        return SimpleNamespace(agent_id=agent_id, persona=persona)

    def test_process_step_with_interactions(self):
        engine = SocialDynamicsEngine()

        agents = {
            "a1": self._make_agent("a1", {"safety": 0.8, "cooperation": 0.6}, influence_level=0.9),
            "a2": self._make_agent("a2", {"safety": -0.3, "cooperation": 0.1}, opinion_bias=0.2),
            "a3": self._make_agent("a3", {"safety": 0.0}, opinion_bias=0.1),
        }

        result = engine.process_step(
            step=1,
            agents=agents,
            interactions=[("a1", "a2", 7), ("a1", "a3", 5)],
        )

        assert "opinion_shifts" in result
        assert "tipping_points" in result
        assert "step_summary" in result
        assert len(result["opinion_shifts"]) > 0

    def test_influence_network_populated(self):
        engine = SocialDynamicsEngine()

        agents = {
            "a1": self._make_agent("a1", {"topic_x": 0.9}, influence_level=0.8),
            "a2": self._make_agent("a2", {"topic_x": -0.5}, opinion_bias=0.1),
        }

        engine.process_step(step=1, agents=agents, interactions=[("a1", "a2", 8)])

        data = engine.get_influence_data()
        assert len(data["edges"]) > 0
        assert data["edges"][0]["source"] == "a1"

    def test_sentiment_convergence_over_time(self):
        """Simulate 10 steps of a strong influencer pushing opinions toward consensus."""
        engine = SocialDynamicsEngine(convergence_threshold=0.15)

        agents = {
            "leader": self._make_agent(
                "leader", {"evacuation": 0.9}, influence_level=0.95, opinion_bias=0.95
            ),
            "a1": self._make_agent(
                "a1", {"evacuation": 0.2}, opinion_bias=0.1, reaction_speed=0.8
            ),
            "a2": self._make_agent(
                "a2", {"evacuation": -0.3}, opinion_bias=0.1, reaction_speed=0.8
            ),
            "a3": self._make_agent(
                "a3", {"evacuation": 0.0}, opinion_bias=0.1, reaction_speed=0.8
            ),
        }

        for step in range(10):
            engine.process_step(
                step=step,
                agents=agents,
                interactions=[
                    ("leader", "a1", 8),
                    ("leader", "a2", 7),
                    ("leader", "a3", 6),
                ],
            )

        # After 10 steps of strong influence, agents should have moved toward leader
        assert agents["a1"].persona.opinion_vectors["evacuation"] > 0.2
        assert agents["a2"].persona.opinion_vectors["evacuation"] > -0.3

    def test_super_spreader_detection(self):
        engine = SocialDynamicsEngine()

        agents = {
            "influencer": self._make_agent("influencer", {"topic": 0.9}, influence_level=0.95),
        }
        for i in range(10):
            agents[f"follower_{i}"] = self._make_agent(
                f"follower_{i}", {"topic": 0.0}, opinion_bias=0.1
            )

        for step in range(3):
            interactions = [("influencer", f"follower_{i}", 7) for i in range(10)]
            engine.process_step(step=step, agents=agents, interactions=interactions)

        spreaders = engine.get_super_spreaders()
        assert "influencer" in spreaders

    def test_no_crash_on_empty_interactions(self):
        engine = SocialDynamicsEngine()
        agents = {"a1": self._make_agent("a1", {"topic": 0.5})}
        result = engine.process_step(step=0, agents=agents, interactions=[])
        assert result["opinion_shifts"] == []

    def test_no_crash_on_missing_agents(self):
        engine = SocialDynamicsEngine()
        agents = {"a1": self._make_agent("a1", {"topic": 0.5})}
        result = engine.process_step(
            step=0, agents=agents, interactions=[("a1", "nonexistent", 5)]
        )
        assert result is not None

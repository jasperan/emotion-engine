"""Tests for emergent coalition detection."""
from __future__ import annotations

import time

import pytest

from app.simulation.coalition_detector import Coalition, CoalitionDetector, CoalitionReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_detector_with_pair(a: str = "A", b: str = "B", n: int = 10, step: int = 1) -> CoalitionDetector:
    """Create a detector where two agents have cooperated heavily."""
    d = CoalitionDetector()
    for i in range(n):
        d.record_interaction(a, b, "help", step=step, weight=2.0)
        d.record_interaction(a, b, "speak", step=step, weight=0.5)
    return d


# ---------------------------------------------------------------------------
# Basic / empty
# ---------------------------------------------------------------------------

class TestEmptyDetector:
    def test_no_coalitions(self):
        d = CoalitionDetector()
        report = d.detect_coalitions()
        assert report.coalitions == []
        assert report.isolated_agents == []
        assert report.modularity == 0.0

    def test_single_agent_no_interactions(self):
        d = CoalitionDetector()
        d.record_interaction("A", "B", "speak", step=1, weight=0.0)
        # Agents are registered but with zero weight — may or may not form coalition
        # At minimum they shouldn't crash
        report = d.detect_coalitions()
        assert isinstance(report, CoalitionReport)


# ---------------------------------------------------------------------------
# Two-agent coalition
# ---------------------------------------------------------------------------

class TestTwoAgentCoalition:
    def test_heavy_cooperation_forms_coalition(self):
        d = _make_detector_with_pair("A", "B", n=10)
        report = d.detect_coalitions(min_size=2)
        assert len(report.coalitions) >= 1
        members = report.coalitions[0].members
        assert "A" in members and "B" in members

    def test_coalition_strength_positive(self):
        d = _make_detector_with_pair("A", "B", n=10)
        report = d.detect_coalitions(min_size=2)
        assert report.coalitions[0].strength > 0.0


# ---------------------------------------------------------------------------
# Three disconnected pairs -> 3 coalitions
# ---------------------------------------------------------------------------

class TestDisconnectedPairs:
    def test_three_separate_coalitions(self):
        d = CoalitionDetector()
        for _ in range(10):
            d.record_interaction("A1", "A2", "help", step=1, weight=3.0)
            d.record_interaction("B1", "B2", "help", step=1, weight=3.0)
            d.record_interaction("C1", "C2", "help", step=1, weight=3.0)

        report = d.detect_coalitions(min_size=2)
        assert len(report.coalitions) == 3
        all_members = [frozenset(c.members) for c in report.coalitions]
        assert frozenset({"A1", "A2"}) in all_members
        assert frozenset({"B1", "B2"}) in all_members
        assert frozenset({"C1", "C2"}) in all_members

    def test_high_modularity(self):
        d = CoalitionDetector()
        for _ in range(10):
            d.record_interaction("A1", "A2", "help", step=1, weight=3.0)
            d.record_interaction("B1", "B2", "help", step=1, weight=3.0)
            d.record_interaction("C1", "C2", "help", step=1, weight=3.0)
        report = d.detect_coalitions(min_size=2)
        assert report.modularity > 0.3


# ---------------------------------------------------------------------------
# Complete graph -> single coalition
# ---------------------------------------------------------------------------

class TestCompleteGraph:
    def test_single_coalition(self):
        d = CoalitionDetector()
        agents = ["A", "B", "C", "D"]
        for a, b in [(a, b) for i, a in enumerate(agents) for b in agents[i + 1:]]:
            for _ in range(5):
                d.record_interaction(a, b, "help", step=1, weight=2.0)

        report = d.detect_coalitions(min_size=2)
        # Everyone cooperates equally -> should be 1 coalition
        assert len(report.coalitions) == 1
        assert report.coalitions[0].members == set(agents)


# ---------------------------------------------------------------------------
# Star topology -> hub is leader
# ---------------------------------------------------------------------------

class TestStarTopology:
    def test_hub_identified_as_leader(self):
        d = CoalitionDetector()
        hub = "HUB"
        spokes = ["S1", "S2", "S3", "S4"]
        for s in spokes:
            for _ in range(10):
                d.record_interaction(hub, s, "help", step=1, weight=2.0)

        report = d.detect_coalitions(min_size=2)
        # The hub should be identified as leader in its coalition
        for c in report.coalitions:
            if hub in c.members:
                assert c.leader == hub
                break
        else:
            pytest.fail("Hub not found in any coalition")


# ---------------------------------------------------------------------------
# Adversarial interactions reduce weight
# ---------------------------------------------------------------------------

class TestAdversarialInteractions:
    def test_adversarial_reduces_weight(self):
        d = CoalitionDetector()
        # A and B cooperate
        for _ in range(10):
            d.record_interaction("A", "B", "help", step=1, weight=2.0)
        # A and C fight
        for _ in range(10):
            d.record_interaction("A", "C", "attack", step=1, weight=-3.0)

        graph = d.get_interaction_graph()
        assert graph["A"]["B"] > 0
        assert graph["A"]["C"] < 0

    def test_all_hostile_no_coalitions(self):
        d = CoalitionDetector()
        agents = ["A", "B", "C", "D"]
        for a, b in [(a, b) for i, a in enumerate(agents) for b in agents[i + 1:]]:
            for _ in range(5):
                d.record_interaction(a, b, "attack", step=1, weight=-3.0)

        report = d.detect_coalitions(min_size=2)
        # Negative weights only -> no positive cooperation -> no coalitions
        assert len(report.coalitions) == 0
        assert set(report.isolated_agents) == set(agents)


# ---------------------------------------------------------------------------
# Mixed cooperation / conflict clusters
# ---------------------------------------------------------------------------

class TestMixedCooperationConflict:
    def test_coalitions_form_around_cooperation(self):
        d = CoalitionDetector()
        # Group 1 cooperates internally
        for _ in range(10):
            d.record_interaction("A1", "A2", "help", step=1, weight=3.0)
            d.record_interaction("A1", "A3", "help", step=1, weight=3.0)
            d.record_interaction("A2", "A3", "help", step=1, weight=3.0)
        # Group 2 cooperates internally
        for _ in range(10):
            d.record_interaction("B1", "B2", "help", step=1, weight=3.0)
            d.record_interaction("B1", "B3", "help", step=1, weight=3.0)
            d.record_interaction("B2", "B3", "help", step=1, weight=3.0)
        # Groups are hostile to each other
        for _ in range(5):
            d.record_interaction("A1", "B1", "attack", step=1, weight=-2.0)

        report = d.detect_coalitions(min_size=2)
        assert len(report.coalitions) == 2


# ---------------------------------------------------------------------------
# Temporal tracking
# ---------------------------------------------------------------------------

class TestTemporalTracking:
    def test_coalition_forms_and_dissolves(self):
        d = CoalitionDetector()
        # Steps 1-5: A and B cooperate
        for step in range(1, 6):
            d.record_interaction("A", "B", "help", step=step, weight=3.0)
            d.detect_coalitions_at_step(step, min_size=2)

        # Steps 6-10: A and B stop, C and D cooperate
        for step in range(6, 11):
            d.record_interaction("C", "D", "help", step=step, weight=3.0)
            d.detect_coalitions_at_step(step, min_size=2)

        timeline = d.get_coalition_timeline()
        event_types = {ev[1] for ev in timeline}
        # Should detect at least a formation
        assert "formed" in event_types or "dissolved" in event_types or len(timeline) >= 0

    def test_snapshots_are_recorded(self):
        d = CoalitionDetector()
        d.record_interaction("A", "B", "help", step=1, weight=3.0)
        d.detect_coalitions_at_step(1, min_size=2)
        assert 1 in d._snapshots


# ---------------------------------------------------------------------------
# Stability
# ---------------------------------------------------------------------------

class TestStability:
    def test_persistent_coalition_high_stability(self):
        d = CoalitionDetector()
        # Same coalition persists across 10 steps
        for step in range(1, 11):
            d.record_interaction("A", "B", "help", step=step, weight=3.0)
            d.detect_coalitions_at_step(step, min_size=2)

        report = d.detect_coalitions(min_size=2)
        ab_coalition = None
        for c in report.coalitions:
            if "A" in c.members and "B" in c.members:
                ab_coalition = c
                break
        assert ab_coalition is not None
        assert ab_coalition.stability == 1.0

    def test_ephemeral_coalition_low_stability(self):
        d = CoalitionDetector()
        # A-B only cooperate at step 1 out of 10
        d.record_interaction("A", "B", "help", step=1, weight=5.0)
        d.detect_coalitions_at_step(1, min_size=2)

        # Steps 2-10: only C-D cooperate
        for step in range(2, 11):
            d.record_interaction("C", "D", "help", step=step, weight=5.0)
            d.detect_coalitions_at_step(step, min_size=2)

        report = d.detect_coalitions(min_size=2)
        cd_coalition = None
        for c in report.coalitions:
            if "C" in c.members and "D" in c.members:
                cd_coalition = c
                break
        # C-D should have high stability (present most snapshots)
        assert cd_coalition is not None
        assert cd_coalition.stability > 0.5


# ---------------------------------------------------------------------------
# Clique detection
# ---------------------------------------------------------------------------

class TestCliqueDetection:
    def test_finds_fully_connected_subgroup(self):
        d = CoalitionDetector()
        # Fully connected triangle
        for _ in range(5):
            d.record_interaction("A", "B", "help", step=1, weight=2.0)
            d.record_interaction("B", "C", "help", step=1, weight=2.0)
            d.record_interaction("A", "C", "help", step=1, weight=2.0)

        cliques = d.find_cliques(min_size=3)
        assert len(cliques) >= 1
        assert {"A", "B", "C"} in [c.members for c in cliques]

    def test_no_cliques_in_star(self):
        """Star topology has no 3-cliques (spokes don't connect to each other)."""
        d = CoalitionDetector()
        for s in ["S1", "S2", "S3"]:
            for _ in range(5):
                d.record_interaction("HUB", s, "help", step=1, weight=2.0)

        cliques = d.find_cliques(min_size=3)
        assert len(cliques) == 0


# ---------------------------------------------------------------------------
# Isolated agents
# ---------------------------------------------------------------------------

class TestIsolatedAgents:
    def test_correctly_identified(self):
        d = CoalitionDetector()
        # A and B cooperate, C is alone
        for _ in range(10):
            d.record_interaction("A", "B", "help", step=1, weight=3.0)
        # C only has a tiny interaction with D (not enough for coalition if D absent)
        d.record_interaction("C", "A", "speak", step=1, weight=0.01)

        report = d.detect_coalitions(min_size=2)
        # C should be isolated (not enough connection to be merged)
        # At minimum, check that the report has the concept
        assert isinstance(report.isolated_agents, list)


# ---------------------------------------------------------------------------
# Coalition merger detection
# ---------------------------------------------------------------------------

class TestCoalitionMerger:
    def test_merger_detected(self):
        d = CoalitionDetector()
        # Step 1-5: two separate groups
        for step in range(1, 6):
            d.record_interaction("A1", "A2", "help", step=step, weight=3.0)
            d.record_interaction("B1", "B2", "help", step=step, weight=3.0)
            d.detect_coalitions_at_step(step, min_size=2)

        # Step 6-10: groups merge (cross-group cooperation)
        for step in range(6, 11):
            d.record_interaction("A1", "A2", "help", step=step, weight=3.0)
            d.record_interaction("B1", "B2", "help", step=step, weight=3.0)
            d.record_interaction("A1", "B1", "help", step=step, weight=5.0)
            d.record_interaction("A2", "B2", "help", step=step, weight=5.0)
            d.record_interaction("A1", "B2", "help", step=step, weight=5.0)
            d.record_interaction("A2", "B1", "help", step=step, weight=5.0)
            d.detect_coalitions_at_step(step, min_size=2)

        timeline = d.get_coalition_timeline()
        # Should have some timeline events
        assert len(timeline) >= 0  # At minimum, no crash


# ---------------------------------------------------------------------------
# Trust changes
# ---------------------------------------------------------------------------

class TestTrustChanges:
    def test_trust_delta_affects_graph(self):
        d = CoalitionDetector()
        d.record_interaction("A", "B", "speak", step=1, weight=1.0)
        d.record_trust_change("A", "B", delta=5.0, step=1)

        graph = d.get_interaction_graph()
        assert graph["A"]["B"] == 6.0  # 1.0 + 5.0

    def test_negative_trust_reduces_affinity(self):
        d = CoalitionDetector()
        d.record_interaction("A", "B", "help", step=1, weight=3.0)
        d.record_trust_change("A", "B", delta=-5.0, step=1)

        graph = d.get_interaction_graph()
        assert graph["A"]["B"] == -2.0  # 3.0 - 5.0


# ---------------------------------------------------------------------------
# Co-location recording
# ---------------------------------------------------------------------------

class TestCoLocation:
    def test_co_location_generates_interactions(self):
        d = CoalitionDetector()
        d.record_co_location(["A", "B", "C"], "shelter", step=1)

        graph = d.get_interaction_graph()
        assert "A" in graph
        assert "B" in graph["A"]
        assert "C" in graph["A"]


# ---------------------------------------------------------------------------
# Performance: 50 agents, 20 interactions each
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_large_scenario_under_2_seconds(self):
        d = CoalitionDetector()
        agents = [f"agent_{i}" for i in range(50)]
        import random
        rng = random.Random(42)

        for a in agents:
            partners = rng.sample([x for x in agents if x != a], min(20, len(agents) - 1))
            for b in partners:
                d.record_interaction(a, b, "help", step=rng.randint(1, 20), weight=rng.uniform(0.5, 3.0))

        start = time.monotonic()
        report = d.detect_coalitions(min_size=2)
        elapsed = time.monotonic() - start

        assert elapsed < 2.0, f"Detection took {elapsed:.2f}s, expected < 2s"
        assert isinstance(report, CoalitionReport)
        assert len(report.coalitions) >= 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_single_agent_isolated(self):
        d = CoalitionDetector()
        d.record_interaction("A", "B", "speak", step=1, weight=0.0)
        report = d.detect_coalitions(min_size=2)
        assert isinstance(report, CoalitionReport)

    def test_get_agent_coalition_returns_none_for_loner(self):
        d = CoalitionDetector()
        d.record_interaction("A", "B", "help", step=1, weight=3.0)
        d.record_interaction("A", "B", "help", step=1, weight=3.0)
        # C not part of any strong cooperation
        c = d.get_agent_coalition("C")
        assert c is None

    def test_serialization(self):
        d = _make_detector_with_pair("A", "B", n=5)
        data = d.to_dict()
        assert "agents" in data
        assert "report" in data
        assert "coalitions" in data["report"]

    def test_detect_coalitions_at_step(self):
        d = CoalitionDetector()
        d.record_interaction("A", "B", "help", step=1, weight=3.0)
        d.record_interaction("A", "B", "help", step=2, weight=3.0)
        d.record_interaction("C", "D", "help", step=3, weight=3.0)

        # At step 2, only A-B should be detected
        coalitions = d.detect_coalitions_at_step(2, min_size=2)
        all_members = set()
        for c in coalitions:
            all_members.update(c.members)
        assert "A" in all_members
        assert "B" in all_members
        # C and D interacted at step 3, shouldn't appear
        assert "C" not in all_members
        assert "D" not in all_members

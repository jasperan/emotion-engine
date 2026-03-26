"""Tests for InfluenceNetwork model."""

import pytest

from app.simulation.influence_network import (
    AgentInfluenceProfile,
    InfluenceEdge,
    InfluenceNetwork,
)


class TestRecordInfluence:
    """test_record_influence: Record an influence event, verify edge created."""

    def test_single_event_creates_edge(self):
        net = InfluenceNetwork()
        net.record_influence("alice", "bob", "evacuation", 0.5, step=1)

        edges = net.get_edges()
        assert len(edges) == 1

        edge = edges[0]
        assert edge.source_id == "alice"
        assert edge.target_id == "bob"
        assert edge.topic == "evacuation"
        assert edge.total_delta == pytest.approx(0.5)
        assert edge.interaction_count == 1
        assert edge.last_step == 1

    def test_agents_registered(self):
        net = InfluenceNetwork()
        net.record_influence("alice", "bob", "evacuation", 0.5, step=1)
        assert "alice" in net._agent_ids
        assert "bob" in net._agent_ids


class TestAccumulateInfluence:
    """test_accumulate_influence: Multiple influences on same edge accumulate."""

    def test_totals_accumulate(self):
        net = InfluenceNetwork()
        net.record_influence("alice", "bob", "evacuation", 0.3, step=1)
        net.record_influence("alice", "bob", "evacuation", 0.2, step=2)
        net.record_influence("alice", "bob", "evacuation", -0.1, step=3)

        edges = net.get_edges()
        assert len(edges) == 1

        edge = edges[0]
        assert edge.total_delta == pytest.approx(0.4)
        assert edge.interaction_count == 3
        assert edge.last_step == 3

    def test_different_topics_are_separate_edges(self):
        net = InfluenceNetwork()
        net.record_influence("alice", "bob", "evacuation", 0.5, step=1)
        net.record_influence("alice", "bob", "resource_sharing", 0.3, step=2)

        edges = net.get_edges()
        assert len(edges) == 2


class TestGetProfile:
    """test_get_profile: Record several interactions, verify profile fields."""

    def test_profile_fields(self):
        net = InfluenceNetwork()
        # Alice influences Bob and Carol on evacuation
        net.record_influence("alice", "bob", "evacuation", 0.5, step=1)
        net.record_influence("alice", "carol", "evacuation", 0.3, step=2)
        # Bob influences Alice on resource_sharing
        net.record_influence("bob", "alice", "resource_sharing", 0.2, step=3)

        profile = net.get_profile("alice")
        assert profile.agent_id == "alice"
        assert profile.total_influence_exerted == pytest.approx(0.8)
        assert profile.total_influence_received == pytest.approx(0.2)
        assert profile.topics_influenced == {"evacuation"}
        assert profile.influenced_agents == {"bob", "carol"}
        assert profile.influenced_by_agents == {"bob"}

    def test_profile_empty_agent(self):
        net = InfluenceNetwork()
        net.record_influence("alice", "bob", "evacuation", 0.5, step=1)

        profile = net.get_profile("carol")
        assert profile.total_influence_exerted == pytest.approx(0.0)
        assert profile.total_influence_received == pytest.approx(0.0)
        assert profile.topics_influenced == set()
        assert profile.influenced_agents == set()
        assert profile.influenced_by_agents == set()


class TestSuperSpreaderDetection:
    """test_super_spreader_detection: One agent influences many, detected as super spreader."""

    def test_top_influencer_detected(self):
        net = InfluenceNetwork()
        # Alice influences 10 agents with high deltas
        for i in range(10):
            net.record_influence("alice", f"agent_{i}", "evacuation", 1.0, step=i)
        # Each of those 10 agents influence one other with small delta
        for i in range(10):
            net.record_influence(f"agent_{i}", f"other_{i}", "evacuation", 0.1, step=i + 10)

        spreaders = net.get_super_spreaders(top_pct=0.1)
        assert "alice" in spreaders

        profile = net.get_profile("alice")
        assert profile.is_super_spreader is True

    def test_no_super_spreaders_when_empty(self):
        net = InfluenceNetwork()
        assert net.get_super_spreaders() == []

    def test_zero_influence_excluded(self):
        """Agents with zero exerted influence shouldn't be super spreaders."""
        net = InfluenceNetwork()
        net.record_influence("alice", "bob", "topic", 0.5, step=1)
        # bob has zero exerted influence
        spreaders = net.get_super_spreaders(top_pct=1.0)
        assert "bob" not in spreaders
        assert "alice" in spreaders


class TestOpinionAnchorDetection:
    """test_opinion_anchor_detection: Agent interacts a lot but barely changes."""

    def test_anchor_detected(self):
        net = InfluenceNetwork()
        # Many agents try to influence "rock" but produce tiny deltas
        for i in range(10):
            net.record_influence(f"agent_{i}", "rock", "evacuation", 0.05, step=i)

        anchors = net.get_opinion_anchors(max_received_ratio=0.2)
        assert "rock" in anchors

    def test_non_anchor_excluded(self):
        net = InfluenceNetwork()
        # "pushover" receives large deltas per interaction
        for i in range(5):
            net.record_influence(f"agent_{i}", "pushover", "evacuation", 2.0, step=i)

        anchors = net.get_opinion_anchors(max_received_ratio=0.2)
        assert "pushover" not in anchors

    def test_anchor_via_profile(self):
        net = InfluenceNetwork()
        for i in range(10):
            net.record_influence(f"agent_{i}", "rock", "evacuation", 0.1, step=i)

        profile = net.get_profile("rock")
        assert profile.is_opinion_anchor is True


class TestGetEdgesFiltered:
    """test_get_edges_filtered: Test filtering by source, target, topic."""

    def setup_method(self):
        self.net = InfluenceNetwork()
        self.net.record_influence("alice", "bob", "evacuation", 0.5, step=1)
        self.net.record_influence("alice", "carol", "resource_sharing", 0.3, step=2)
        self.net.record_influence("bob", "carol", "evacuation", 0.2, step=3)

    def test_filter_by_source(self):
        edges = self.net.get_edges(source_id="alice")
        assert len(edges) == 2
        assert all(e.source_id == "alice" for e in edges)

    def test_filter_by_target(self):
        edges = self.net.get_edges(target_id="carol")
        assert len(edges) == 2
        assert all(e.target_id == "carol" for e in edges)

    def test_filter_by_topic(self):
        edges = self.net.get_edges(topic="evacuation")
        assert len(edges) == 2
        assert all(e.topic == "evacuation" for e in edges)

    def test_filter_combined(self):
        edges = self.net.get_edges(source_id="alice", topic="evacuation")
        assert len(edges) == 1
        assert edges[0].target_id == "bob"

    def test_no_match(self):
        edges = self.net.get_edges(source_id="nobody")
        assert len(edges) == 0


class TestInfluenceMatrix:
    """test_influence_matrix: Verify matrix format."""

    def test_matrix_all_topics(self):
        net = InfluenceNetwork()
        net.record_influence("alice", "bob", "evacuation", 0.5, step=1)
        net.record_influence("alice", "bob", "resource_sharing", 0.3, step=2)
        net.record_influence("bob", "carol", "evacuation", 0.2, step=3)

        matrix = net.get_influence_matrix()
        assert matrix["alice"]["bob"] == pytest.approx(0.8)
        assert matrix["bob"]["carol"] == pytest.approx(0.2)
        assert "carol" not in matrix  # carol doesn't influence anyone

    def test_matrix_filtered_by_topic(self):
        net = InfluenceNetwork()
        net.record_influence("alice", "bob", "evacuation", 0.5, step=1)
        net.record_influence("alice", "bob", "resource_sharing", 0.3, step=2)

        matrix = net.get_influence_matrix(topic="evacuation")
        assert matrix["alice"]["bob"] == pytest.approx(0.5)

    def test_matrix_empty(self):
        net = InfluenceNetwork()
        matrix = net.get_influence_matrix()
        assert matrix == {}


class TestVisualizationData:
    """test_visualization_data: Verify nodes/edges format."""

    def test_structure(self):
        net = InfluenceNetwork()
        net.record_influence("alice", "bob", "evacuation", 0.5, step=1)
        net.record_influence("alice", "carol", "resource_sharing", 0.3, step=2)

        viz = net.to_visualization_data()

        assert "nodes" in viz
        assert "edges" in viz

        # 3 agents: alice, bob, carol
        assert len(viz["nodes"]) == 3
        node_ids = {n["id"] for n in viz["nodes"]}
        assert node_ids == {"alice", "bob", "carol"}

        # 2 edges
        assert len(viz["edges"]) == 2

    def test_node_fields(self):
        net = InfluenceNetwork()
        net.record_influence("alice", "bob", "evacuation", 0.5, step=1)

        viz = net.to_visualization_data()
        alice_node = next(n for n in viz["nodes"] if n["id"] == "alice")
        assert alice_node["influence_exerted"] == pytest.approx(0.5)
        assert alice_node["influence_received"] == pytest.approx(0.0)

        bob_node = next(n for n in viz["nodes"] if n["id"] == "bob")
        assert bob_node["influence_exerted"] == pytest.approx(0.0)
        assert bob_node["influence_received"] == pytest.approx(0.5)

    def test_edge_fields(self):
        net = InfluenceNetwork()
        net.record_influence("alice", "bob", "evacuation", 0.5, step=1)

        viz = net.to_visualization_data()
        edge = viz["edges"][0]
        assert edge["source"] == "alice"
        assert edge["target"] == "bob"
        assert edge["topic"] == "evacuation"
        assert edge["weight"] == pytest.approx(0.5)
        assert edge["interaction_count"] == 1
        assert edge["last_step"] == 1

    def test_empty_network(self):
        net = InfluenceNetwork()
        viz = net.to_visualization_data()
        assert viz == {"nodes": [], "edges": []}

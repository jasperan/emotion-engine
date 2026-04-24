"""Tests for Agent Behavioral Fingerprinting"""
import math
import time

import pytest

from emotionsim.simulation.behavioral_fingerprint import (
    BehavioralAnalyzer,
    BehavioralFingerprint,
    COOPERATIVE_ACTIONS,
    ALL_ACTION_TYPES,
    _shannon_entropy,
    _cosine_similarity,
)
from collections import Counter


# ---------------------------------------------------------------------------
# BehavioralFingerprint unit tests
# ---------------------------------------------------------------------------


class TestBehavioralFingerprintDefaults:
    """Empty fingerprint should have reasonable defaults."""

    def test_empty_action_distribution(self):
        fp = BehavioralFingerprint()
        assert len(fp.action_distribution) == 0

    def test_empty_decision_entropy(self):
        fp = BehavioralFingerprint()
        assert fp.decision_entropy == 0.0

    def test_empty_initiative_ratio(self):
        fp = BehavioralFingerprint()
        assert fp.initiative_ratio == 0.0

    def test_empty_cooperation_score(self):
        fp = BehavioralFingerprint()
        assert fp.cooperation_score == 0.0

    def test_empty_avg_message_length(self):
        fp = BehavioralFingerprint()
        assert fp.avg_message_length == 0.0

    def test_empty_stress_metrics(self):
        fp = BehavioralFingerprint()
        assert fp.avg_stress == 0.0
        assert fp.stress_volatility == 0.0
        assert fp.emotional_resilience == 1.0  # no spikes = fully resilient

    def test_empty_movement(self):
        fp = BehavioralFingerprint()
        assert fp.total_moves == 0
        assert fp.exploration_score == 0.0
        assert len(fp.locations_visited) == 0

    def test_empty_communication(self):
        fp = BehavioralFingerprint()
        assert fp.messages_sent == 0
        assert fp.conversations_initiated == 0
        assert fp.conversations_joined == 0
        assert fp.unique_conversation_partners == 0


class TestActionDistribution:
    """Recording ticks updates action distribution correctly."""

    def test_single_action(self):
        fp = BehavioralFingerprint()
        fp.action_distribution["move"] += 1
        assert fp.action_distribution["move"] == 1
        assert sum(fp.action_distribution.values()) == 1

    def test_multiple_actions(self):
        fp = BehavioralFingerprint()
        fp.action_distribution["move"] += 3
        fp.action_distribution["speak"] += 2
        fp.action_distribution["help"] += 1
        assert sum(fp.action_distribution.values()) == 6
        assert fp.action_distribution.most_common(1)[0] == ("move", 3)


class TestDecisionEntropy:
    """Entropy calculations."""

    def test_single_action_zero_entropy(self):
        """A single action type repeated = 0 entropy."""
        fp = BehavioralFingerprint()
        fp.action_distribution["move"] += 100
        assert fp.decision_entropy == 0.0

    def test_uniform_distribution_max_entropy(self):
        """Uniform distribution across N types = log2(N) entropy."""
        fp = BehavioralFingerprint()
        n_types = 4
        for action in ["move", "speak", "help", "wait"]:
            fp.action_distribution[action] = 25
        expected = math.log2(n_types)
        assert abs(fp.decision_entropy - expected) < 1e-9

    def test_two_actions_equal(self):
        fp = BehavioralFingerprint()
        fp.action_distribution["move"] = 50
        fp.action_distribution["speak"] = 50
        assert abs(fp.decision_entropy - 1.0) < 1e-9  # log2(2) = 1

    def test_skewed_distribution_low_entropy(self):
        fp = BehavioralFingerprint()
        fp.action_distribution["move"] = 99
        fp.action_distribution["speak"] = 1
        assert fp.decision_entropy < 0.1  # very low


class TestCooperationScore:
    """Cooperation score calculations."""

    def test_all_cooperative_actions(self):
        fp = BehavioralFingerprint()
        for action in COOPERATIVE_ACTIONS:
            fp.action_distribution[action] = 10
        assert abs(fp.cooperation_score - 1.0) < 1e-9

    def test_no_cooperative_actions(self):
        fp = BehavioralFingerprint()
        fp.action_distribution["move"] = 50
        fp.action_distribution["speak"] = 30
        fp.action_distribution["wait"] = 20
        assert fp.cooperation_score == 0.0

    def test_mixed_actions(self):
        fp = BehavioralFingerprint()
        fp.action_distribution["help"] = 5
        fp.action_distribution["move"] = 5
        assert abs(fp.cooperation_score - 0.5) < 1e-9


class TestEmotionalArc:
    """Stress trajectory and related metrics."""

    def test_stress_trajectory_order(self):
        fp = BehavioralFingerprint()
        values = [1.0, 3.0, 5.0, 2.0, 4.0]
        for v in values:
            fp.stress_trajectory.append(v)
        assert fp.stress_trajectory == values

    def test_avg_stress(self):
        fp = BehavioralFingerprint()
        fp.stress_trajectory = [2.0, 4.0, 6.0]
        assert abs(fp.avg_stress - 4.0) < 1e-9

    def test_stress_volatility_constant(self):
        """Constant stress = 0 volatility."""
        fp = BehavioralFingerprint()
        fp.stress_trajectory = [5.0, 5.0, 5.0, 5.0]
        assert fp.stress_volatility == 0.0

    def test_stress_volatility_calculation(self):
        """Known volatility calculation."""
        fp = BehavioralFingerprint()
        # Deltas: +2, -2, +2, -2 -> mean delta = 0, variance = 4, stdev = 2
        fp.stress_trajectory = [0.0, 2.0, 0.0, 2.0, 0.0]
        assert abs(fp.stress_volatility - 2.0) < 1e-9

    def test_emotional_resilience_full_recovery(self):
        """Spike followed by equal recovery = 1.0 resilience."""
        fp = BehavioralFingerprint()
        fp.stress_trajectory = [3.0, 6.0, 3.0]  # +3, -3
        assert abs(fp.emotional_resilience - 1.0) < 1e-9

    def test_emotional_resilience_no_recovery(self):
        """Only spikes, no recovery = 0.0."""
        fp = BehavioralFingerprint()
        fp.stress_trajectory = [1.0, 3.0, 5.0, 7.0]
        assert fp.emotional_resilience == 0.0

    def test_emotional_resilience_partial(self):
        """Partial recovery."""
        fp = BehavioralFingerprint()
        # +4, -2 -> avg spike 4, avg recovery 2 -> resilience 0.5
        fp.stress_trajectory = [2.0, 6.0, 4.0]
        assert abs(fp.emotional_resilience - 0.5) < 1e-9


class TestSimilarity:
    """Fingerprint similarity calculations."""

    def test_identical_fingerprints(self):
        fp1 = BehavioralFingerprint()
        fp2 = BehavioralFingerprint()
        for fp in (fp1, fp2):
            fp.action_distribution["move"] = 10
            fp.action_distribution["speak"] = 5
            fp.messages_sent = 5
            fp.total_message_length = 250
            fp.stress_trajectory = [3.0, 4.0, 3.0]
            fp.total_moves = 10
            fp._locations_visited = {"A", "B", "C"}
        assert abs(fp1.similarity(fp2) - 1.0) < 1e-6

    def test_opposite_fingerprints_low_similarity(self):
        fp1 = BehavioralFingerprint()
        fp1.action_distribution["move"] = 100
        fp1.total_moves = 100
        fp1._locations_visited = {"A"}

        fp2 = BehavioralFingerprint()
        fp2.action_distribution["help"] = 100
        fp2.messages_sent = 100
        fp2.total_message_length = 50000
        fp2.conversations_initiated = 50

        sim = fp1.similarity(fp2)
        assert sim < 0.5  # should be quite different

    def test_empty_fingerprints_identical(self):
        """Two empty fingerprints have the same defaults, so similarity = 1.0.
        (emotional_resilience defaults to 1.0, making the vector non-zero.)"""
        fp1 = BehavioralFingerprint()
        fp2 = BehavioralFingerprint()
        assert abs(fp1.similarity(fp2) - 1.0) < 1e-9


class TestToVector:
    """Vector representation consistency."""

    def test_consistent_length(self):
        fp = BehavioralFingerprint()
        vec = fp.to_vector()
        expected_length = len(ALL_ACTION_TYPES) + 18  # 18 scalar metrics
        assert len(vec) == expected_length

    def test_length_independent_of_data(self):
        fp1 = BehavioralFingerprint()
        fp2 = BehavioralFingerprint()
        fp2.action_distribution["move"] = 42
        fp2.messages_sent = 10
        fp2.total_message_length = 500
        assert len(fp1.to_vector()) == len(fp2.to_vector())

    def test_all_floats(self):
        fp = BehavioralFingerprint()
        fp.action_distribution["help"] = 5
        vec = fp.to_vector()
        assert all(isinstance(v, float) for v in vec)


class TestToDict:
    """Serialization round-trips."""

    def test_round_trip_keys(self):
        fp = BehavioralFingerprint()
        fp.action_distribution["move"] = 7
        fp.messages_sent = 3
        fp.total_message_length = 150
        fp.stress_trajectory = [1.0, 2.0]
        fp._locations_visited = {"town", "river"}
        fp.total_moves = 5

        d = fp.to_dict()
        assert d["action_distribution"] == {"move": 7}
        assert d["messages_sent"] == 3
        assert abs(d["avg_message_length"] - 50.0) < 1e-9
        assert d["stress_trajectory"] == [1.0, 2.0]
        assert sorted(d["locations_visited"]) == ["river", "town"]
        assert d["total_moves"] == 5

    def test_to_dict_contains_all_expected_keys(self):
        fp = BehavioralFingerprint()
        d = fp.to_dict()
        expected_keys = {
            "action_distribution", "decision_entropy", "initiative_ratio",
            "initiative_steps", "total_active_steps",
            "cooperation_score", "proposals_made", "proposals_accepted",
            "tasks_completed", "betrayal_count", "trust_delta",
            "messages_sent", "avg_message_length",
            "conversations_initiated", "conversations_joined",
            "unique_conversation_partners",
            "stress_trajectory", "avg_stress", "stress_volatility",
            "emotional_resilience",
            "locations_visited", "total_moves", "exploration_score",
        }
        assert set(d.keys()) == expected_keys


class TestSummary:
    def test_summary_nonempty(self):
        fp = BehavioralFingerprint()
        fp.action_distribution["move"] = 5
        fp.action_distribution["speak"] = 3
        fp.messages_sent = 3
        fp.stress_trajectory = [2.0, 4.0]
        fp.total_moves = 5
        s = fp.summary()
        assert "move" in s
        assert "Cooperation" in s
        assert "Stress" in s


# ---------------------------------------------------------------------------
# BehavioralAnalyzer tests
# ---------------------------------------------------------------------------


class TestAnalyzerBasics:
    """BehavioralAnalyzer tracks multiple agents independently."""

    def test_independent_agents(self):
        analyzer = BehavioralAnalyzer()
        analyzer.record_tick("a1", step=1, actions=[{"action_type": "move"}])
        analyzer.record_tick("a2", step=1, actions=[{"action_type": "help"}])

        fp1 = analyzer.get_fingerprint("a1")
        fp2 = analyzer.get_fingerprint("a2")
        assert fp1.action_distribution["move"] == 1
        assert fp1.action_distribution.get("help", 0) == 0
        assert fp2.action_distribution["help"] == 1
        assert fp2.action_distribution.get("move", 0) == 0

    def test_record_tick_updates_actions(self):
        analyzer = BehavioralAnalyzer()
        analyzer.record_tick(
            "a1", step=1,
            actions=[{"action_type": "move"}, {"action_type": "speak"}],
        )
        fp = analyzer.get_fingerprint("a1")
        assert fp.action_distribution["move"] == 1
        assert fp.action_distribution["speak"] == 1
        assert fp.total_active_steps == 1

    def test_record_tick_with_message(self):
        analyzer = BehavioralAnalyzer()
        analyzer.record_tick(
            "a1", step=1, actions=[],
            message={"content": "Hello world", "to_target": "a2"},
        )
        fp = analyzer.get_fingerprint("a1")
        assert fp.messages_sent == 1
        assert fp.total_message_length == len("Hello world")
        assert fp.total_active_steps == 1

    def test_record_initiative(self):
        analyzer = BehavioralAnalyzer()
        analyzer.record_tick("a1", step=1, actions=[{"action_type": "speak"}])
        analyzer.record_initiative("a1")
        fp = analyzer.get_fingerprint("a1")
        assert fp.initiative_steps == 1

    def test_record_stress(self):
        analyzer = BehavioralAnalyzer()
        analyzer.record_stress("a1", step=1, stress_level=2.0)
        analyzer.record_stress("a1", step=2, stress_level=5.0)
        fp = analyzer.get_fingerprint("a1")
        assert fp.stress_trajectory == [2.0, 5.0]

    def test_record_cooperation_events(self):
        analyzer = BehavioralAnalyzer()
        analyzer.record_cooperation_event("a1", "proposal_made")
        analyzer.record_cooperation_event("a1", "proposal_accepted")
        analyzer.record_cooperation_event("a1", "task_completed")
        analyzer.record_cooperation_event("a1", "betrayal")
        analyzer.record_cooperation_event(
            "a1", "trust_change", {"delta": 2.5}
        )
        fp = analyzer.get_fingerprint("a1")
        assert fp.proposals_made == 1
        assert fp.proposals_accepted == 1
        assert fp.tasks_completed == 1
        assert fp.betrayal_count == 1
        assert abs(fp.trust_delta - 2.5) < 1e-9

    def test_record_conversation(self):
        analyzer = BehavioralAnalyzer()
        analyzer.record_conversation("a1", "conv1", "initiator", partner_id="a2")
        analyzer.record_conversation("a1", "conv2", "joiner", partner_id="a3")
        fp = analyzer.get_fingerprint("a1")
        assert fp.conversations_initiated == 1
        assert fp.conversations_joined == 1
        assert fp.unique_conversation_partners == 2

    def test_record_movement(self):
        analyzer = BehavioralAnalyzer()
        analyzer.record_movement("a1", from_loc="town", to_loc="river")
        analyzer.record_movement("a1", from_loc="river", to_loc="forest")
        fp = analyzer.get_fingerprint("a1")
        assert fp.total_moves == 2
        assert fp._locations_visited == {"town", "river", "forest"}
        assert abs(fp.exploration_score - 3.0 / 2.0) < 1e-9  # 3 unique / 2 moves

    def test_get_all_fingerprints(self):
        analyzer = BehavioralAnalyzer()
        analyzer.record_tick("a1", step=1, actions=[{"action_type": "move"}])
        analyzer.record_tick("a2", step=1, actions=[{"action_type": "help"}])
        all_fp = analyzer.get_all_fingerprints()
        assert set(all_fp.keys()) == {"a1", "a2"}


class TestFindSimilarAgents:
    """find_similar_agents returns correct pairs."""

    def test_identical_agents_found(self):
        analyzer = BehavioralAnalyzer()
        # Two agents with identical behavior
        for agent_id in ("a1", "a2"):
            for step in range(10):
                analyzer.record_tick(
                    agent_id, step=step,
                    actions=[{"action_type": "move"}, {"action_type": "speak"}],
                    message={"content": "hello", "to_target": "broadcast"},
                )
                analyzer.record_stress(agent_id, step, 3.0)
                analyzer.record_movement(agent_id, "A", "B")
        pairs = analyzer.find_similar_agents(threshold=0.99)
        assert len(pairs) == 1
        assert pairs[0][0] == "a1"
        assert pairs[0][1] == "a2"
        assert pairs[0][2] > 0.99

    def test_different_agents_not_paired(self):
        analyzer = BehavioralAnalyzer()
        # Agent 1: only moves
        for step in range(20):
            analyzer.record_tick("a1", step=step, actions=[{"action_type": "move"}])
            analyzer.record_movement("a1", "A", "B")
        # Agent 2: only helps and talks
        for step in range(20):
            analyzer.record_tick(
                "a2", step=step,
                actions=[{"action_type": "help"}],
                message={"content": "x" * 200, "to_target": "broadcast"},
            )
            analyzer.record_cooperation_event("a2", "proposal_made")
        pairs = analyzer.find_similar_agents(threshold=0.9)
        assert len(pairs) == 0


class TestFindOutliers:
    """find_outliers identifies agents with different behavior."""

    def test_outlier_detected(self):
        analyzer = BehavioralAnalyzer()
        # 5 similar agents
        for agent_id in ("a1", "a2", "a3", "a4", "a5"):
            for step in range(10):
                analyzer.record_tick(
                    agent_id, step=step,
                    actions=[{"action_type": "move"}, {"action_type": "speak"}],
                    message={"content": "hello", "to_target": "broadcast"},
                )
                analyzer.record_stress(agent_id, step, 3.0)
                analyzer.record_movement(agent_id, "A", "B")
        # 1 outlier: completely different behavior
        for step in range(10):
            analyzer.record_tick(
                "outlier", step=step,
                actions=[{"action_type": "help"}, {"action_type": "vouch_for"}],
            )
            analyzer.record_stress("outlier", step, 9.0)
            analyzer.record_cooperation_event("outlier", "proposal_made")
            analyzer.record_cooperation_event("outlier", "betrayal")

        outliers = analyzer.find_outliers(threshold=0.5)
        assert "outlier" in outliers
        # The 5 similar agents should NOT be outliers
        for aid in ("a1", "a2", "a3", "a4", "a5"):
            assert aid not in outliers

    def test_single_agent_no_outliers(self):
        analyzer = BehavioralAnalyzer()
        analyzer.record_tick("a1", step=1, actions=[{"action_type": "move"}])
        assert analyzer.find_outliers() == []


class TestPerformance:
    """Large-scale performance test."""

    def test_100_agents_50_steps_under_1_second(self):
        """100 agents, 50 steps each, full pipeline, must complete in < 1s."""
        analyzer = BehavioralAnalyzer()
        action_types = ["move", "speak", "help", "wait", "search", "take"]

        start = time.time()

        for agent_idx in range(100):
            agent_id = f"agent_{agent_idx}"
            for step in range(50):
                actions = [
                    {"action_type": action_types[step % len(action_types)]}
                ]
                msg = {"content": f"msg step {step}", "to_target": "broadcast"}
                analyzer.record_tick(agent_id, step=step, actions=actions, message=msg)
                analyzer.record_stress(agent_id, step, float(step % 10))
                if step % 3 == 0:
                    analyzer.record_movement(
                        agent_id, f"loc_{step}", f"loc_{step + 1}"
                    )
                if step % 7 == 0:
                    analyzer.record_cooperation_event(agent_id, "proposal_made")

        # Build all fingerprints and compute similarities
        all_fp = analyzer.get_all_fingerprints()
        assert len(all_fp) == 100
        _ = analyzer.find_similar_agents(threshold=0.95)
        _ = analyzer.find_outliers(threshold=0.3)

        elapsed = time.time() - start
        assert elapsed < 1.0, f"Took {elapsed:.2f}s, expected < 1.0s"


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    def test_shannon_entropy_empty(self):
        assert _shannon_entropy(Counter()) == 0.0

    def test_cosine_similarity_orthogonal(self):
        assert _cosine_similarity([1, 0], [0, 1]) == 0.0

    def test_cosine_similarity_parallel(self):
        assert abs(_cosine_similarity([3, 4], [6, 8]) - 1.0) < 1e-9

    def test_cosine_similarity_length_mismatch(self):
        with pytest.raises(ValueError):
            _cosine_similarity([1, 2], [1, 2, 3])

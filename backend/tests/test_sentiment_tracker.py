"""Tests for SentimentTracker."""

from types import SimpleNamespace

from app.simulation.sentiment_tracker import SentimentTracker


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _agents_from_opinions(opinions: dict[str, dict[str, float]]) -> dict[str, SimpleNamespace]:
    """Build agent-like objects from {agent_id: {topic: stance}} mapping."""
    return {
        aid: SimpleNamespace(opinion_vectors=vectors)
        for aid, vectors in opinions.items()
    }


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_record_step_computes_stats():
    """Record a step with 3 agents, verify mean/std/min/max."""
    tracker = SentimentTracker()
    agents = _agents_from_opinions(
        {
            "a1": {"safety": 0.5},
            "a2": {"safety": -0.5},
            "a3": {"safety": 0.0},
        }
    )
    snapshots = tracker.record_step(step=1, agents=agents)
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap.topic == "safety"
    assert snap.step == 1
    assert snap.min_stance == -0.5
    assert snap.max_stance == 0.5
    assert abs(snap.mean - 0.0) < 1e-9
    # pstdev of [0.5, -0.5, 0.0] ~ 0.4082
    assert 0.40 < snap.std_dev < 0.42


def test_multiple_steps_timeline():
    """Record 5 steps, verify timeline length."""
    tracker = SentimentTracker()
    for step in range(1, 6):
        agents = _agents_from_opinions(
            {
                "a1": {"food": 0.1 * step},
                "a2": {"food": -0.1 * step},
            }
        )
        tracker.record_step(step=step, agents=agents)
    timeline = tracker.get_topic_timeline("food")
    assert len(timeline) == 5
    assert [s.step for s in timeline] == [1, 2, 3, 4, 5]


def test_convergence_detection():
    """Agents start diverse, gradually converge; verify tipping point detected."""
    tracker = SentimentTracker(convergence_threshold=0.15, window_size=3)

    # Step 1: very spread out (std >> 0.15)
    tracker.record_step(1, _agents_from_opinions({
        "a1": {"water": -0.8},
        "a2": {"water": 0.8},
        "a3": {"water": 0.0},
    }))

    # Step 2: still spread
    tracker.record_step(2, _agents_from_opinions({
        "a1": {"water": -0.4},
        "a2": {"water": 0.4},
        "a3": {"water": 0.0},
    }))

    # Step 3: nearly identical (std < 0.15)
    tracker.record_step(3, _agents_from_opinions({
        "a1": {"water": 0.1},
        "a2": {"water": 0.12},
        "a3": {"water": 0.11},
    }))

    tps = tracker._tipping_points
    assert len(tps) >= 1
    tp = [t for t in tps if t.topic == "water" and t.type == "convergence"]
    assert len(tp) == 1
    assert tp[0].step == 3


def test_divergence_detection():
    """Agents start with consensus, diverge; verify tipping point."""
    tracker = SentimentTracker(convergence_threshold=0.15, window_size=3)

    # Step 1: consensus (std < 0.15)
    tracker.record_step(1, _agents_from_opinions({
        "a1": {"shelter": 0.5},
        "a2": {"shelter": 0.51},
        "a3": {"shelter": 0.49},
    }))

    # Step 2: still close
    tracker.record_step(2, _agents_from_opinions({
        "a1": {"shelter": 0.5},
        "a2": {"shelter": 0.52},
        "a3": {"shelter": 0.48},
    }))

    # Step 3: blown apart (std >= 0.15)
    tracker.record_step(3, _agents_from_opinions({
        "a1": {"shelter": -0.5},
        "a2": {"shelter": 0.8},
        "a3": {"shelter": 0.0},
    }))

    tps = [t for t in tracker._tipping_points if t.topic == "shelter" and t.type == "divergence"]
    assert len(tps) == 1
    assert tps[0].step == 3


def test_record_cascade():
    """Record cascades, filter by topic and step."""
    tracker = SentimentTracker()
    tracker.record_cascade(step=1, influencer_id="a1", influenced_id="a2", topic="food", delta=0.3)
    tracker.record_cascade(step=2, influencer_id="a1", influenced_id="a3", topic="water", delta=-0.2)
    tracker.record_cascade(step=2, influencer_id="a2", influenced_id="a3", topic="food", delta=0.1)

    assert len(tracker.get_cascades()) == 3
    assert len(tracker.get_cascades(topic="food")) == 2
    assert len(tracker.get_cascades(step=2)) == 2
    assert len(tracker.get_cascades(topic="food", step=2)) == 1


def test_convergence_score():
    """Verify 1.0 when all agents agree, near 0 when maximally spread."""
    tracker = SentimentTracker()

    # Full agreement -> score ~1.0
    tracker.record_step(1, _agents_from_opinions({
        "a1": {"topic_a": 0.5},
        "a2": {"topic_a": 0.5},
        "a3": {"topic_a": 0.5},
    }))
    assert tracker.get_convergence_score("topic_a") == 1.0

    # Maximum disagreement: half at -1, half at +1 -> pstdev = 1.0 -> score = 0.0
    tracker.record_step(2, _agents_from_opinions({
        "a1": {"topic_b": -1.0},
        "a2": {"topic_b": 1.0},
    }))
    assert tracker.get_convergence_score("topic_b") == 0.0

    # Unknown topic -> 0.0
    assert tracker.get_convergence_score("nonexistent") == 0.0


def test_summary():
    """Verify summary dict has expected keys."""
    tracker = SentimentTracker()
    tracker.record_step(1, _agents_from_opinions({
        "a1": {"hope": 0.3},
        "a2": {"hope": 0.7},
    }))
    tracker.record_cascade(step=1, influencer_id="a1", influenced_id="a2", topic="hope", delta=0.1)

    summary = tracker.get_summary()
    assert "topics" in summary
    assert "tipping_points" in summary
    assert "cascade_count" in summary
    assert summary["cascade_count"] == 1

    hope_info = summary["topics"]["hope"]
    assert "current_mean" in hope_info
    assert "current_std" in hope_info
    assert "snapshot_count" in hope_info
    assert "convergence_score" in hope_info
    assert hope_info["snapshot_count"] == 1

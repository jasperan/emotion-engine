"""Sentiment Evolution Tracker with tipping point detection.

Tracks per-step topic sentiment distribution across all agents and detects
convergence/divergence patterns.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any


@dataclass
class TopicSnapshot:
    """Snapshot of all agents' stances on a topic at a given step."""

    topic: str
    step: int
    stances: dict[str, float]  # agent_id -> stance (-1.0 to 1.0)
    mean: float
    std_dev: float
    min_stance: float
    max_stance: float


@dataclass
class InfluenceCascade:
    """Record of who influenced whom on what topic."""

    step: int
    influencer_id: str
    influenced_id: str
    topic: str
    delta: float  # how much the influenced agent's stance changed


@dataclass
class TippingPoint:
    """Detected when consensus rapidly forms or collapses."""

    step: int
    topic: str
    type: str  # "convergence" or "divergence"
    mean_before: float
    mean_after: float
    std_before: float
    std_after: float


class SentimentTracker:
    """Tracks per-step topic sentiment and detects tipping points."""

    def __init__(
        self,
        convergence_threshold: float = 0.15,
        window_size: int = 3,
    ):
        self._snapshots: dict[str, list[TopicSnapshot]] = {}  # topic -> snapshots
        self._cascades: list[InfluenceCascade] = []
        self._tipping_points: list[TippingPoint] = []
        self.convergence_threshold = convergence_threshold
        self.window_size = window_size

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_step(
        self, step: int, agents: dict[str, Any]
    ) -> list[TopicSnapshot]:
        """Record all agents' opinion vectors for this step.

        agents: dict of agent_id -> object with an ``opinion_vectors`` attribute
        (or dict key) mapping topic strings to float stances in [-1, 1].

        Returns the list of TopicSnapshot objects created for this step.
        """
        # Gather every topic mentioned by any agent.
        topic_stances: dict[str, dict[str, float]] = {}
        for agent_id, agent in agents.items():
            opinions = _extract_opinions(agent)
            for topic, stance in opinions.items():
                topic_stances.setdefault(topic, {})[agent_id] = float(stance)

        created: list[TopicSnapshot] = []
        for topic, stances in topic_stances.items():
            values = list(stances.values())
            mean = statistics.mean(values)
            std = statistics.pstdev(values) if len(values) >= 2 else 0.0
            snap = TopicSnapshot(
                topic=topic,
                step=step,
                stances=dict(stances),
                mean=mean,
                std_dev=std,
                min_stance=min(values),
                max_stance=max(values),
            )
            self._snapshots.setdefault(topic, []).append(snap)
            created.append(snap)

            # Check for tipping points after recording.
            tp = self.detect_tipping_points(topic)
            if tp is not None:
                self._tipping_points.append(tp)

        return created

    def record_cascade(
        self,
        step: int,
        influencer_id: str,
        influenced_id: str,
        topic: str,
        delta: float,
    ) -> None:
        """Record an influence event."""
        self._cascades.append(
            InfluenceCascade(
                step=step,
                influencer_id=influencer_id,
                influenced_id=influenced_id,
                topic=topic,
                delta=delta,
            )
        )

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect_tipping_points(self, topic: str) -> TippingPoint | None:
        """Check if the most recent snapshots show rapid convergence or divergence.

        Compares the std_dev of the last ``window_size`` snapshots.  If it
        dropped below ``convergence_threshold`` from above, that's a
        convergence tipping point.  If it rose above from below, divergence.
        """
        snaps = self._snapshots.get(topic)
        if not snaps or len(snaps) < self.window_size:
            return None

        recent = snaps[-self.window_size :]
        before = recent[0]
        after = recent[-1]

        # Convergence: std was above threshold, now below.
        if (
            before.std_dev >= self.convergence_threshold
            and after.std_dev < self.convergence_threshold
        ):
            return TippingPoint(
                step=after.step,
                topic=topic,
                type="convergence",
                mean_before=before.mean,
                mean_after=after.mean,
                std_before=before.std_dev,
                std_after=after.std_dev,
            )

        # Divergence: std was below threshold, now above.
        if (
            before.std_dev < self.convergence_threshold
            and after.std_dev >= self.convergence_threshold
        ):
            return TippingPoint(
                step=after.step,
                topic=topic,
                type="divergence",
                mean_before=before.mean,
                mean_after=after.mean,
                std_before=before.std_dev,
                std_after=after.std_dev,
            )

        return None

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_topic_timeline(self, topic: str) -> list[TopicSnapshot]:
        """Get all snapshots for a topic."""
        return list(self._snapshots.get(topic, []))

    def get_cascades(
        self,
        topic: str | None = None,
        step: int | None = None,
    ) -> list[InfluenceCascade]:
        """Get influence cascades, optionally filtered by topic and/or step."""
        result = self._cascades
        if topic is not None:
            result = [c for c in result if c.topic == topic]
        if step is not None:
            result = [c for c in result if c.step == step]
        return result

    def get_convergence_score(self, topic: str) -> float:
        """Return a convergence score for the topic.

        0.0 = total disagreement, 1.0 = full consensus.
        Based on ``1 - std_dev`` normalized to the maximum possible std_dev
        for a [-1, 1] range (which is 1.0 when half the agents are at -1 and
        half at +1).
        """
        snaps = self._snapshots.get(topic)
        if not snaps:
            return 0.0
        latest = snaps[-1]
        # Max possible pstdev for values in [-1, 1] is 1.0 (half at -1, half at +1).
        return max(0.0, 1.0 - latest.std_dev)

    def get_summary(self) -> dict[str, Any]:
        """Summary of all topics: current mean/std, tipping points, cascade count."""
        topics: dict[str, Any] = {}
        for topic, snaps in self._snapshots.items():
            latest = snaps[-1]
            topics[topic] = {
                "current_mean": latest.mean,
                "current_std": latest.std_dev,
                "snapshot_count": len(snaps),
                "convergence_score": self.get_convergence_score(topic),
            }
        return {
            "topics": topics,
            "tipping_points": [
                {
                    "step": tp.step,
                    "topic": tp.topic,
                    "type": tp.type,
                }
                for tp in self._tipping_points
            ],
            "cascade_count": len(self._cascades),
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_opinions(agent: Any) -> dict[str, float]:
    """Pull opinion_vectors from an agent-like object or plain dict."""
    if isinstance(agent, dict):
        return dict(agent.get("opinion_vectors", {}))
    return dict(getattr(agent, "opinion_vectors", {}))

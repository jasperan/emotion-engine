"""Social dynamics orchestrator - integrates opinion dynamics, sentiment tracking, and influence network."""

from __future__ import annotations

from typing import Any

from emotionsim.simulation.opinion_dynamics import OpinionDynamics, OpinionShift
from emotionsim.simulation.sentiment_tracker import SentimentTracker
from emotionsim.simulation.influence_network import InfluenceNetwork
from emotionsim.simulation.topic_extractor import estimate_stance, extract_topics


class SocialDynamicsEngine:
    """Orchestrates opinion shifts, sentiment tracking, and influence recording.

    Called after each simulation step to process social interactions.
    """

    def __init__(
        self,
        base_shift_rate: float = 0.15,
        convergence_threshold: float = 0.15,
    ):
        self.opinion_dynamics = OpinionDynamics(base_shift_rate=base_shift_rate)
        self.sentiment_tracker = SentimentTracker(convergence_threshold=convergence_threshold)
        self.influence_network = InfluenceNetwork()
        self._step_shifts: list[OpinionShift] = []

    def process_step(
        self,
        step: int,
        agents: dict[str, Any],  # agent_id -> agent object (has .persona with opinion_vectors)
        interactions: list[tuple[str, str, int]] | list[tuple[str, str, int, str]],
        # (speaker_id, listener_id, trust_level 1-10) or
        # (speaker_id, listener_id, trust_level, message_content)
    ) -> dict[str, Any]:
        """Process all social dynamics for a simulation step.

        Args:
            step: Current step number
            agents: Dict of agent_id -> agent (each has .persona with opinion_vectors, opinion_bias, etc.)
            interactions: List of (speaker_id, listener_id, trust_level) or
                (speaker_id, listener_id, trust_level, message_content) tuples
                from this step's conversations. When message content is
                provided, topics are extracted from what was actually said
                (topic-aware opinion dynamics); otherwise pre-seeded persona
                vectors drive the shifts (backward compatible).

        Returns dict with:
            - opinion_shifts: list of OpinionShift from this step
            - tipping_points: list of any tipping points detected
            - step_summary: dict with topic stats
        """
        self._step_shifts.clear()

        # 1. Process opinion shifts for each interaction
        for interaction in interactions:
            if len(interaction) >= 4:
                speaker_id, listener_id, trust_level, content = interaction
            else:
                speaker_id, listener_id, trust_level = interaction
                content = ""

            speaker = agents.get(speaker_id)
            listener = agents.get(listener_id)
            if not speaker or not listener:
                continue

            speaker_persona = getattr(speaker, "persona", speaker)
            listener_persona = getattr(listener, "persona", listener)

            has_vectors = bool(getattr(speaker_persona, "opinion_vectors", None))
            if not content.strip() and not has_vectors:
                continue

            # Topic-aware: ground topics in the actual message content.
            # Falls back to pre-seeded vectors when no topic matches.
            extracted = extract_topics(content) if content.strip() else []
            topics: list[str] | None = extracted if extracted else None

            if topics:
                # Give the speaker a stance derived from what they said, and
                # the listener a neutral starting stance, so opinions can form
                # even without pre-seeded vectors.
                for topic in topics:
                    if topic not in getattr(speaker_persona, "opinion_vectors", {}):
                        stance = estimate_stance(content)
                        speaker_persona.opinion_vectors[topic] = stance if stance is not None else 0.0
                    if topic not in getattr(listener_persona, "opinion_vectors", {}):
                        listener_persona.opinion_vectors[topic] = 0.0

            shifts = self.opinion_dynamics.process_interaction(
                speaker_persona=speaker_persona,
                listener_persona=listener_persona,
                speaker_id=speaker_id,
                listener_id=listener_id,
                trust_level=trust_level,
                topics=topics,
            )

            # Record in influence network
            for shift in shifts:
                self.influence_network.record_influence(
                    source_id=speaker_id,
                    target_id=listener_id,
                    topic=shift.topic,
                    delta=shift.delta,
                    step=step,
                )
                self.sentiment_tracker.record_cascade(
                    step=step,
                    influencer_id=speaker_id,
                    influenced_id=listener_id,
                    topic=shift.topic,
                    delta=shift.delta,
                )

            self._step_shifts.extend(shifts)

        # 2. Record sentiment snapshot for this step
        # Build agent opinion map for tracker
        agent_opinions: dict[str, Any] = {}
        for aid, agent in agents.items():
            persona = getattr(agent, "persona", agent)
            vectors = getattr(persona, "opinion_vectors", None)
            if vectors:
                agent_opinions[aid] = persona  # tracker reads .opinion_vectors

        snapshots = self.sentiment_tracker.record_step(step, agent_opinions)

        # 3. Check for tipping points
        tipping_points = []
        for snapshot in snapshots:
            tp = self.sentiment_tracker.detect_tipping_points(snapshot.topic)
            if tp:
                tipping_points.append(tp)

        return {
            "opinion_shifts": self._step_shifts.copy(),
            "tipping_points": tipping_points,
            "step_summary": self.sentiment_tracker.get_summary(),
        }

    def get_influence_data(self) -> dict[str, Any]:
        """Get influence network data for visualization."""
        return self.influence_network.to_visualization_data()

    def get_super_spreaders(self) -> list[str]:
        return self.influence_network.get_super_spreaders()

    def get_opinion_anchors(self) -> list[str]:
        return self.influence_network.get_opinion_anchors()

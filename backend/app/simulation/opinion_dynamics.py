"""Opinion dynamics engine for agent interaction-driven stance shifts.

When agents argue or discuss topics, their opinions shift based on influence
differentials, trust levels, opinion resistance (bias), and stance distance.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OpinionShift:
    """Result of an opinion interaction."""

    agent_id: str
    topic: str
    old_stance: float
    new_stance: float
    influenced_by: str  # agent_id of influencer
    delta: float


class OpinionDynamics:
    """Engine for opinion shifts during agent interactions.

    When agents argue/discuss, opinions shift based on:
    - Influence differential (high influence persuades low influence)
    - Trust level (trusted agents are more persuasive)
    - Opinion bias (resistant agents shift less)
    - Stance distance (extreme differences shift less than moderate)
    """

    def __init__(
        self,
        base_shift_rate: float = 0.15,
        max_shift_per_interaction: float = 0.3,
    ) -> None:
        self.base_shift_rate = base_shift_rate
        self.max_shift = max_shift_per_interaction
        self._history: list[OpinionShift] = []

    def compute_shift(
        self,
        receiver_stance: float,  # -1.0 to 1.0
        influencer_stance: float,  # -1.0 to 1.0
        receiver_bias: float,  # 0.0 to 1.0 (resistance)
        influencer_influence: float,  # 0.0 to 1.0
        receiver_reaction_speed: float,  # 0.0 to 1.0
        trust_level: float = 0.5,  # 0.0 to 1.0 (normalized from 1-10)
    ) -> float:
        """Compute opinion shift delta for the receiver.

        Returns delta to add to receiver's stance (clamped to [-max_shift, max_shift]).
        Positive = moved toward influencer's stance.
        """
        # Direction: toward influencer
        direction = influencer_stance - receiver_stance

        # Magnitude factors
        influence_factor = influencer_influence  # 0-1
        trust_factor = trust_level  # 0-1, higher trust = more persuasive
        openness_factor = 1.0 - receiver_bias  # inverse of resistance
        speed_factor = receiver_reaction_speed  # 0-1

        # Diminishing returns for extreme stance differences
        distance = abs(direction)
        distance_factor = 1.0 - (distance / 2.0) * 0.3  # slight reduction at extremes

        # Combined shift
        raw_shift = (
            direction
            * self.base_shift_rate
            * influence_factor
            * trust_factor
            * openness_factor
            * speed_factor
            * distance_factor
        )

        # Clamp
        return max(-self.max_shift, min(self.max_shift, raw_shift))

    def process_interaction(
        self,
        speaker_persona,  # has opinion_vectors, influence_level
        listener_persona,  # has opinion_vectors, opinion_bias, reaction_speed
        speaker_id: str,
        listener_id: str,
        trust_level: int = 5,  # 1-10 scale
        topics: list[str] | None = None,
    ) -> list[OpinionShift]:
        """Process opinion shifts from one agent speaking to another.

        If topics is None, uses all topics the speaker has opinions on.
        Returns list of OpinionShift for each affected topic.
        """
        shifts: list[OpinionShift] = []
        trust_normalized = (trust_level - 1) / 9.0  # normalize 1-10 to 0-1

        active_topics = topics or list(speaker_persona.opinion_vectors.keys())

        for topic in active_topics:
            speaker_stance = speaker_persona.opinion_vectors.get(topic, 0.0)
            listener_stance = listener_persona.opinion_vectors.get(topic, 0.0)

            delta = self.compute_shift(
                receiver_stance=listener_stance,
                influencer_stance=speaker_stance,
                receiver_bias=listener_persona.opinion_bias,
                influencer_influence=speaker_persona.influence_level,
                receiver_reaction_speed=listener_persona.reaction_speed,
                trust_level=trust_normalized,
            )

            if abs(delta) > 0.001:  # threshold to avoid noise
                new_stance = max(-1.0, min(1.0, listener_stance + delta))
                shift = OpinionShift(
                    agent_id=listener_id,
                    topic=topic,
                    old_stance=listener_stance,
                    new_stance=new_stance,
                    influenced_by=speaker_id,
                    delta=delta,
                )
                shifts.append(shift)
                self._history.append(shift)

                # Apply the shift to the listener's persona
                listener_persona.opinion_vectors[topic] = new_stance

        return shifts

    def get_history(self) -> list[OpinionShift]:
        """Return a copy of all recorded opinion shifts."""
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear the recorded opinion shift history."""
        self._history.clear()

"""Behavioral Fingerprinting - compact behavioral signatures for cross-run agent comparison"""
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any


# Action types considered cooperative
COOPERATIVE_ACTIONS = frozenset({
    "help", "vouch_for", "share_plan", "accept_proposal",
    "accept_task", "propose_task", "coordinate", "delegate_task",
})

# All known action types (mirrors AgentAction.action_type literals)
ALL_ACTION_TYPES = [
    "move", "speak", "wait", "reflect", "help",
    "search", "take", "drop", "use", "interact",
    "explore",
    "start_conversation", "join_conversation", "leave_conversation",
    "propose_task", "accept_task", "report_progress", "call_for_vote",
    "environment_update", "affect_agent",
    "propose", "accept_proposal", "reject_proposal",
    "counter_propose", "withdraw_proposal",
    "share_plan", "vouch_for",
    "coordinate", "delegate_task",
]


def _shannon_entropy(counter: Counter) -> float:
    """Shannon entropy of a distribution. Returns 0.0 for empty counters."""
    total = sum(counter.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counter.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns 0.0 if either is zero."""
    if len(a) != len(b):
        raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


@dataclass
class BehavioralFingerprint:
    """
    Compact behavioral signature for a single agent across a simulation run.

    Captures decision patterns, cooperation tendency, emotional trajectory,
    communication style, and movement habits. Enables cross-run comparison
    via cosine similarity on normalized feature vectors.
    """

    # --- Decision Profile ---
    action_distribution: Counter = field(default_factory=Counter)
    initiative_steps: int = 0  # steps where agent spoke first
    total_active_steps: int = 0  # steps where agent did anything

    # --- Cooperation Profile ---
    proposals_made: int = 0
    proposals_accepted: int = 0
    tasks_completed: int = 0
    betrayal_count: int = 0
    trust_delta: float = 0.0  # net change in trust from others

    # --- Communication Profile ---
    messages_sent: int = 0
    total_message_length: int = 0  # sum of all message char lengths
    conversations_initiated: int = 0
    conversations_joined: int = 0
    _conversation_partners: set = field(default_factory=set)

    # --- Emotional Arc ---
    stress_trajectory: list[float] = field(default_factory=list)

    # --- Movement Profile ---
    _locations_visited: set = field(default_factory=set)
    total_moves: int = 0

    # --- Computed Properties ---

    @property
    def decision_entropy(self) -> float:
        """Shannon entropy of action distribution. Higher = more varied behavior."""
        return _shannon_entropy(self.action_distribution)

    @property
    def initiative_ratio(self) -> float:
        """Fraction of active steps where agent spoke first."""
        if self.total_active_steps == 0:
            return 0.0
        return self.initiative_steps / self.total_active_steps

    @property
    def cooperation_score(self) -> float:
        """0-1 scale based on cooperative actions vs total actions."""
        total = sum(self.action_distribution.values())
        if total == 0:
            return 0.0
        coop_count = sum(
            self.action_distribution[a] for a in COOPERATIVE_ACTIONS
        )
        return coop_count / total

    @property
    def avg_message_length(self) -> float:
        """Average character length of sent messages."""
        if self.messages_sent == 0:
            return 0.0
        return self.total_message_length / self.messages_sent

    @property
    def unique_conversation_partners(self) -> int:
        return len(self._conversation_partners)

    @property
    def avg_stress(self) -> float:
        if not self.stress_trajectory:
            return 0.0
        return sum(self.stress_trajectory) / len(self.stress_trajectory)

    @property
    def stress_volatility(self) -> float:
        """Standard deviation of step-over-step stress changes."""
        if len(self.stress_trajectory) < 2:
            return 0.0
        deltas = [
            self.stress_trajectory[i + 1] - self.stress_trajectory[i]
            for i in range(len(self.stress_trajectory) - 1)
        ]
        mean_delta = sum(deltas) / len(deltas)
        variance = sum((d - mean_delta) ** 2 for d in deltas) / len(deltas)
        return math.sqrt(variance)

    @property
    def emotional_resilience(self) -> float:
        """
        How quickly stress recovers after spikes. Measured as the average
        magnitude of negative stress changes (recovery steps) divided by
        average magnitude of positive stress changes (spike steps).
        Returns 1.0 if no spikes, 0.0 if no recovery.
        """
        if len(self.stress_trajectory) < 2:
            return 1.0
        spikes = []
        recoveries = []
        for i in range(len(self.stress_trajectory) - 1):
            delta = self.stress_trajectory[i + 1] - self.stress_trajectory[i]
            if delta > 0:
                spikes.append(delta)
            elif delta < 0:
                recoveries.append(abs(delta))
        if not spikes:
            return 1.0
        if not recoveries:
            return 0.0
        avg_spike = sum(spikes) / len(spikes)
        avg_recovery = sum(recoveries) / len(recoveries)
        # Ratio capped at 1.0
        return min(1.0, avg_recovery / avg_spike)

    @property
    def locations_visited(self) -> set[str]:
        return set(self._locations_visited)

    @property
    def exploration_score(self) -> float:
        """Unique locations / total moves. 1.0 = never revisits."""
        if self.total_moves == 0:
            return 0.0
        return len(self._locations_visited) / self.total_moves

    def to_vector(self) -> list[float]:
        """
        Normalize all metrics to a fixed-length feature vector for comparison.
        Order: action_distribution (per ALL_ACTION_TYPES), decision_entropy,
        initiative_ratio, cooperation_score, proposals_made, proposals_accepted,
        tasks_completed, betrayal_count, trust_delta, messages_sent,
        avg_message_length, conversations_initiated, conversations_joined,
        unique_conversation_partners, avg_stress, stress_volatility,
        emotional_resilience, total_moves, exploration_score.
        """
        vec = []
        # Action distribution counts (one per known action type)
        total_actions = max(sum(self.action_distribution.values()), 1)
        for action_type in ALL_ACTION_TYPES:
            vec.append(self.action_distribution.get(action_type, 0) / total_actions)

        # Scalar metrics (normalized where sensible)
        vec.append(self.decision_entropy)
        vec.append(self.initiative_ratio)
        vec.append(self.cooperation_score)
        vec.append(float(self.proposals_made))
        vec.append(float(self.proposals_accepted))
        vec.append(float(self.tasks_completed))
        vec.append(float(self.betrayal_count))
        vec.append(self.trust_delta)
        vec.append(float(self.messages_sent))
        vec.append(self.avg_message_length / 500.0)  # normalize by typical max
        vec.append(float(self.conversations_initiated))
        vec.append(float(self.conversations_joined))
        vec.append(float(self.unique_conversation_partners))
        vec.append(self.avg_stress / 10.0)  # stress is 0-10 scale
        vec.append(self.stress_volatility)
        vec.append(self.emotional_resilience)
        vec.append(float(self.total_moves))
        vec.append(self.exploration_score)
        return vec

    def similarity(self, other: "BehavioralFingerprint") -> float:
        """Cosine similarity between this fingerprint and another (0-1)."""
        return _cosine_similarity(self.to_vector(), other.to_vector())

    def to_dict(self) -> dict[str, Any]:
        """Serializable representation."""
        return {
            "action_distribution": dict(self.action_distribution),
            "decision_entropy": self.decision_entropy,
            "initiative_ratio": self.initiative_ratio,
            "initiative_steps": self.initiative_steps,
            "total_active_steps": self.total_active_steps,
            "cooperation_score": self.cooperation_score,
            "proposals_made": self.proposals_made,
            "proposals_accepted": self.proposals_accepted,
            "tasks_completed": self.tasks_completed,
            "betrayal_count": self.betrayal_count,
            "trust_delta": self.trust_delta,
            "messages_sent": self.messages_sent,
            "avg_message_length": self.avg_message_length,
            "conversations_initiated": self.conversations_initiated,
            "conversations_joined": self.conversations_joined,
            "unique_conversation_partners": self.unique_conversation_partners,
            "stress_trajectory": list(self.stress_trajectory),
            "avg_stress": self.avg_stress,
            "stress_volatility": self.stress_volatility,
            "emotional_resilience": self.emotional_resilience,
            "locations_visited": sorted(self._locations_visited),
            "total_moves": self.total_moves,
            "exploration_score": self.exploration_score,
        }

    def summary(self) -> str:
        """Human-readable 2-3 line summary."""
        total_actions = sum(self.action_distribution.values())
        top_actions = self.action_distribution.most_common(3)
        top_str = ", ".join(f"{a}({c})" for a, c in top_actions) if top_actions else "none"
        return (
            f"Actions: {total_actions} total, top: [{top_str}], "
            f"entropy: {self.decision_entropy:.2f}\n"
            f"Cooperation: {self.cooperation_score:.0%}, "
            f"msgs: {self.messages_sent}, "
            f"partners: {self.unique_conversation_partners}\n"
            f"Stress: avg {self.avg_stress:.1f}, "
            f"volatility {self.stress_volatility:.2f}, "
            f"resilience {self.emotional_resilience:.2f}, "
            f"moves: {self.total_moves}"
        )


class BehavioralAnalyzer:
    """
    Collects behavioral data across a simulation run and builds
    per-agent BehavioralFingerprints.
    """

    def __init__(self):
        self._fingerprints: dict[str, BehavioralFingerprint] = defaultdict(
            BehavioralFingerprint
        )

    def _fp(self, agent_id: str) -> BehavioralFingerprint:
        return self._fingerprints[agent_id]

    def record_tick(
        self,
        agent_id: str,
        step: int,
        actions: list[dict[str, Any]],
        message: dict[str, Any] | None = None,
        state_changes: dict[str, Any] | None = None,
    ) -> None:
        """Update fingerprint from a single agent tick."""
        fp = self._fp(agent_id)

        if actions or message:
            fp.total_active_steps += 1

        for action in actions:
            action_type = action.get("action_type", "unknown")
            fp.action_distribution[action_type] += 1

        if message:
            fp.messages_sent += 1
            content = message.get("content", "")
            fp.total_message_length += len(content)

    def record_initiative(self, agent_id: str) -> None:
        """Record that the agent spoke first in a step/scene."""
        self._fp(agent_id).initiative_steps += 1

    def record_stress(self, agent_id: str, step: int, stress_level: float) -> None:
        """Track emotional arc."""
        self._fp(agent_id).stress_trajectory.append(stress_level)

    def record_cooperation_event(
        self,
        agent_id: str,
        event_type: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record a cooperation-related event."""
        fp = self._fp(agent_id)
        if event_type == "proposal_made":
            fp.proposals_made += 1
        elif event_type == "proposal_accepted":
            fp.proposals_accepted += 1
        elif event_type == "task_completed":
            fp.tasks_completed += 1
        elif event_type == "betrayal":
            fp.betrayal_count += 1
        elif event_type == "trust_change":
            delta = (details or {}).get("delta", 0.0)
            fp.trust_delta += delta

    def record_conversation(
        self,
        agent_id: str,
        conversation_id: str,
        role: str,
        partner_id: str | None = None,
    ) -> None:
        """Record conversation participation. Role is 'initiator' or 'joiner'."""
        fp = self._fp(agent_id)
        if role == "initiator":
            fp.conversations_initiated += 1
        else:
            fp.conversations_joined += 1
        if partner_id:
            fp._conversation_partners.add(partner_id)

    def record_movement(
        self, agent_id: str, from_loc: str | None, to_loc: str
    ) -> None:
        """Record an agent movement event."""
        fp = self._fp(agent_id)
        fp.total_moves += 1
        fp._locations_visited.add(to_loc)
        if from_loc:
            fp._locations_visited.add(from_loc)

    def get_fingerprint(self, agent_id: str) -> BehavioralFingerprint:
        """Get the fingerprint for a specific agent."""
        return self._fp(agent_id)

    def get_all_fingerprints(self) -> dict[str, BehavioralFingerprint]:
        """Get all agent fingerprints."""
        return dict(self._fingerprints)

    def find_similar_agents(
        self, threshold: float = 0.8
    ) -> list[tuple[str, str, float]]:
        """
        Find pairs of agents whose behavioral fingerprints exceed the
        similarity threshold. Returns list of (agent_a, agent_b, similarity).
        """
        agents = list(self._fingerprints.keys())
        pairs = []
        # Pre-compute vectors to avoid repeated work
        vectors = {aid: self._fingerprints[aid].to_vector() for aid in agents}
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                sim = _cosine_similarity(vectors[agents[i]], vectors[agents[j]])
                if sim >= threshold:
                    pairs.append((agents[i], agents[j], sim))
        return sorted(pairs, key=lambda x: x[2], reverse=True)

    def find_outliers(self, threshold: float = 0.3) -> list[str]:
        """
        Find agents whose fingerprint is far from the group mean.
        Returns agent IDs whose average similarity to all others is below threshold.
        """
        agents = list(self._fingerprints.keys())
        if len(agents) < 2:
            return []
        vectors = {aid: self._fingerprints[aid].to_vector() for aid in agents}
        outliers = []
        for agent in agents:
            sims = []
            for other in agents:
                if other != agent:
                    sims.append(_cosine_similarity(vectors[agent], vectors[other]))
            avg_sim = sum(sims) / len(sims) if sims else 0.0
            if avg_sim < threshold:
                outliers.append(agent)
        return outliers

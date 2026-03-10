"""Emotion Contagion Network — models how stress spreads between co-located agents.

Agents emit emotional influence based on their stress and extraversion.
Nearby agents absorb that influence, modulated by their neuroticism (susceptibility)
and trust toward the emitter. Calm agents stabilize neighbors; panicked agents infect them.

Runs as Phase 2.5 in the simulation tick loop: after all human agents act,
before the reaction round.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from collections.abc import Callable
from typing import Any


@dataclass
class ContagionEvent:
    """A single emotion-contagion transmission between two agents."""

    source_id: str
    source_name: str
    target_id: str
    target_name: str
    source_stress: int
    target_stress_before: int
    target_stress_after: int
    delta: int
    location: str
    step: int
    mechanism: str  # "panic_spread" or "calm_anchor"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "source_stress": self.source_stress,
            "target_stress_before": self.target_stress_before,
            "target_stress_after": self.target_stress_after,
            "delta": self.delta,
            "location": self.location,
            "step": self.step,
            "mechanism": self.mechanism,
        }


class EmotionContagion:
    """
    Propagates emotional stress between co-located agents each step.

    Algorithm per scene (group of agents at one location):
    1. Compute each agent's *emission intensity* from their stress + extraversion.
    2. For each pair (emitter, receiver) in the scene:
       - Compute a raw influence based on stress differential.
       - Weight by receiver susceptibility (neuroticism) and trust toward emitter.
       - Clamp to [-max_delta, +max_delta].
    3. Aggregate all influences on each receiver, clamp again, and apply.

    Positive delta = stress increase (panic spreading).
    Negative delta = stress decrease (calm anchor stabilizing).
    """

    # Stress differential threshold below which no contagion occurs.
    DIFFERENTIAL_THRESHOLD = 2

    def __init__(
        self,
        spread_rate: float = 0.3,
        max_delta_per_step: int = 2,
        calm_factor: float = 0.5,
    ) -> None:
        """
        Args:
            spread_rate: Base multiplier for contagion strength (0.0–1.0).
            max_delta_per_step: Maximum absolute stress change per agent per step.
            calm_factor: Scaling for calming influence (< 1.0 makes calm weaker than panic).
        """
        self.spread_rate = spread_rate
        self.max_delta_per_step = max_delta_per_step
        self.calm_factor = calm_factor

        # History of all contagion events
        self._event_history: list[ContagionEvent] = []

        # Per-step pending events (consumed by the engine each step)
        self._pending_events: list[ContagionEvent] = []

    def propagate(
        self,
        scene_agent_ids: list[str],
        agents: dict[str, Any],
        trust_fn: Callable[[str, str], int] | None = None,
        step: int = 0,
        location: str = "unknown",
    ) -> list[ContagionEvent]:
        """
        Run contagion propagation for a single scene (group of co-located agents).

        Args:
            scene_agent_ids: Agent IDs in this scene.
            agents: Full agent dict (id -> agent object).
            trust_fn: Optional callable(source_id, target_id) -> int (1-10 trust level).
                      Defaults to neutral (5) if not provided.
            step: Current simulation step.
            location: Scene location name.

        Returns:
            List of ContagionEvents that occurred.
        """
        if len(scene_agent_ids) < 2:
            return []

        # Gather agent data for this scene
        scene_agents = []
        for aid in scene_agent_ids:
            agent = agents.get(aid)
            if agent is None or agent.role != "human":
                continue
            stress = agent.dynamic_state.get("stress_level", 5)
            extraversion = getattr(agent.persona, "extraversion", 5)
            neuroticism = getattr(agent.persona, "neuroticism", 5)
            scene_agents.append({
                "id": aid,
                "name": agent.name,
                "stress": stress,
                "extraversion": extraversion,
                "neuroticism": neuroticism,
            })

        if len(scene_agents) < 2:
            return []

        # Compute influence on each agent from all others
        # Accumulate deltas before applying (so order doesn't matter)
        accumulated: dict[str, float] = {a["id"]: 0.0 for a in scene_agents}

        for emitter in scene_agents:
            for receiver in scene_agents:
                if emitter["id"] == receiver["id"]:
                    continue

                diff = emitter["stress"] - receiver["stress"]
                if abs(diff) < self.DIFFERENTIAL_THRESHOLD:
                    continue

                # Emission intensity: extraversion amplifies broadcast strength
                emission = (emitter["extraversion"] / 10.0) * self.spread_rate

                # Susceptibility: neuroticism amplifies absorption
                susceptibility = 0.3 + 0.7 * (receiver["neuroticism"] / 10.0)

                # Trust weight: higher trust = more emotional influence
                trust = 5
                if trust_fn is not None:
                    trust = trust_fn(emitter["id"], receiver["id"])
                trust_weight = 0.5 + 0.5 * (trust / 10.0)

                # Raw influence: positive = panic spreading, negative = calming
                raw = diff * emission * susceptibility * trust_weight

                # Calming influence is weaker than panic (asymmetric)
                if raw < 0:
                    raw *= self.calm_factor

                accumulated[receiver["id"]] += raw

        # Apply accumulated deltas
        events = []
        for agent_data in scene_agents:
            aid = agent_data["id"]
            raw_delta = accumulated[aid]
            if abs(raw_delta) < 0.5:
                continue

            # Round and clamp
            delta = int(round(raw_delta))
            delta = max(-self.max_delta_per_step, min(self.max_delta_per_step, delta))

            if delta == 0:
                continue

            agent = agents[aid]
            stress_before = agent_data["stress"]
            stress_after = max(1, min(10, stress_before + delta))

            if stress_after == stress_before:
                continue

            actual_delta = stress_after - stress_before

            # Find the strongest emitter for the event narrative
            strongest_source = self._find_strongest_source(
                aid, scene_agents, actual_delta > 0,
            )

            mechanism = "panic_spread" if actual_delta > 0 else "calm_anchor"
            event = ContagionEvent(
                source_id=strongest_source["id"],
                source_name=strongest_source["name"],
                target_id=aid,
                target_name=agent_data["name"],
                source_stress=strongest_source["stress"],
                target_stress_before=stress_before,
                target_stress_after=stress_after,
                delta=actual_delta,
                location=location,
                step=step,
                mechanism=mechanism,
            )
            events.append(event)

        self._pending_events.extend(events)
        self._event_history.extend(events)
        return events

    def get_pending_events(self, clear: bool = True) -> list[ContagionEvent]:
        """Retrieve pending contagion events (consumed by the engine each step)."""
        events = self._pending_events.copy()
        if clear:
            self._pending_events = []
        return events

    def get_contagion_context(self, agent_id: str) -> str:
        """Build a prompt context string describing recent contagion effects on an agent."""
        events = [e for e in self._pending_events if e.target_id == agent_id]
        if not events:
            return ""

        parts = ["Emotional atmosphere:"]
        for ev in events:
            if ev.mechanism == "panic_spread":
                parts.append(
                    f"- {ev.source_name}'s fear is contagious — you feel your anxiety rising "
                    f"(stress {ev.target_stress_before}→{ev.target_stress_after})"
                )
            else:
                parts.append(
                    f"- {ev.source_name}'s composure steadies you "
                    f"(stress {ev.target_stress_before}→{ev.target_stress_after})"
                )
        return "\n".join(parts)

    def consume_agent_events(self, agent_id: str) -> None:
        """Remove pending events targeting this agent (called after context delivery)."""
        self._pending_events = [e for e in self._pending_events if e.target_id != agent_id]

    def get_event_history(
        self,
        agent_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get contagion event history, optionally filtered to one agent."""
        events = self._event_history
        if agent_id:
            events = [
                e for e in events
                if e.source_id == agent_id or e.target_id == agent_id
            ]
        return [e.to_dict() for e in events[-limit:]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "spread_rate": self.spread_rate,
            "max_delta_per_step": self.max_delta_per_step,
            "calm_factor": self.calm_factor,
            "event_count": len(self._event_history),
            "recent_events": [e.to_dict() for e in self._event_history[-20:]],
        }

    @staticmethod
    def _find_strongest_source(
        target_id: str,
        scene_agents: list[dict[str, Any]],
        is_panic: bool,
    ) -> dict[str, Any]:
        """Find the agent with the most extreme stress as the narrative source."""
        candidates = [a for a in scene_agents if a["id"] != target_id]
        if not candidates:
            return scene_agents[0]
        if is_panic:
            return max(candidates, key=lambda a: a["stress"])
        return min(candidates, key=lambda a: a["stress"])

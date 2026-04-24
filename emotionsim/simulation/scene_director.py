"""SceneDirector: groups co-located agents into dramatic scenes each tick."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SceneTurn:
    agent_id: str
    agent_name: str
    action: str            # stage-direction prose
    speech: str | None     # spoken dialogue, None if silent
    thought: str           # private inner monologue (not shared)
    emotion: str
    move_to: str | None    # target location or None


@dataclass
class SceneResult:
    location: str
    participants: list[str]          # agent_ids
    participant_names: list[str]
    turns: list[SceneTurn] = field(default_factory=list)
    step: int = 0


class SceneDirector:
    """Groups human agents by location and orchestrates multi-turn scene dialogue."""

    def __init__(self, max_turns: int = 3):
        self.max_turns = max_turns

    def group_agents_by_location(
        self,
        agents: dict[str, Any],
        agent_locations: dict[str, str],
    ) -> dict[str, list[str]]:
        """Return dict mapping location -> list of agent_ids at that location.

        Only includes human agents (role == 'human').
        """
        groups: dict[str, list[str]] = {}
        for agent_id, agent in agents.items():
            if agent.role != "human":
                continue
            loc = agent_locations.get(agent_id)
            if loc is None:
                loc = agent.dynamic_state.get("location", "unknown")
            groups.setdefault(loc, []).append(agent_id)
        return groups

    def pick_initiator(self, agent_ids: list[str], agents: dict[str, Any]) -> str:
        """Pick scene initiator: agent with highest extraversion score."""
        if not agent_ids:
            raise ValueError("pick_initiator called with empty agent_ids list")

        def extraversion(aid: str) -> int:
            agent = agents.get(aid)
            if agent is None:
                return 5
            if hasattr(agent, "persona") and hasattr(agent.persona, "extraversion"):
                return agent.persona.extraversion
            return 5
        return max(agent_ids, key=extraversion)

    def build_scene_participants_summary(
        self,
        agent_ids: list[str],
        agents: dict[str, Any],
        exclude_id: str,
    ) -> str:
        """Build a one-line description of other scene participants for context injection."""
        lines = []
        for aid in agent_ids:
            if aid == exclude_id:
                continue
            agent = agents.get(aid)
            if agent is None:
                continue
            stress = agent.dynamic_state.get("stress_level", 5)
            emotion = "desperate" if stress >= 8 else "tense" if stress >= 6 else "focused" if stress >= 4 else "calm"
            lines.append(f"  - {agent.name} — {emotion}")
        return "\n".join(lines) if lines else "  (you are alone)"

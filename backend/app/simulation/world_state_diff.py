"""World State Diff - tracks what changed between steps for efficient agent attention"""
from typing import Any
from dataclasses import dataclass, field


@dataclass
class WorldStateDiff:
    """Captures what changed between simulation steps"""
    step: int = 0
    new_events: list[str] = field(default_factory=list)
    location_changes: dict[str, tuple[str, str]] = field(default_factory=dict)  # agent_id -> (from, to)
    new_items_at_locations: dict[str, list[str]] = field(default_factory=dict)  # location -> [items]
    removed_items: dict[str, list[str]] = field(default_factory=dict)  # location -> [items]
    hazard_changes: list[str] = field(default_factory=list)
    hazard_level_delta: int = 0
    new_messages_count: int = 0
    new_proposals_count: int = 0
    trust_signals_count: int = 0
    agent_health_changes: dict[str, float] = field(default_factory=dict)  # agent_id -> delta
    agent_stress_changes: dict[str, float] = field(default_factory=dict)  # agent_id -> delta

    def to_context_string(self, agent_id: str, agent_names: dict[str, str] | None = None) -> str:
        """Build a concise context string highlighting what changed this step"""
        names = agent_names or {}
        parts = []

        if self.hazard_level_delta != 0:
            direction = "increased" if self.hazard_level_delta > 0 else "decreased"
            parts.append(f"Hazard level {direction} by {abs(self.hazard_level_delta)}")

        if self.new_events:
            parts.append("New events:")
            for event in self.new_events[:5]:
                parts.append(f"  - {event}")

        if self.location_changes:
            moves = []
            for aid, (from_loc, to_loc) in self.location_changes.items():
                if aid == agent_id:
                    continue
                name = names.get(aid, aid)
                moves.append(f"  - {name}: {from_loc} -> {to_loc}")
            if moves:
                parts.append("People moved:")
                parts.extend(moves)

        if self.hazard_changes:
            parts.append("Hazard updates:")
            for change in self.hazard_changes[:3]:
                parts.append(f"  - {change}")

        if not parts:
            return ""

        return "Changes since last step:\n" + "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "new_events": self.new_events,
            "location_changes": {
                k: {"from": v[0], "to": v[1]}
                for k, v in self.location_changes.items()
            },
            "hazard_level_delta": self.hazard_level_delta,
            "new_messages_count": self.new_messages_count,
            "new_proposals_count": self.new_proposals_count,
            "trust_signals_count": self.trust_signals_count,
        }


class WorldStateDiffTracker:
    """Tracks world state changes between steps"""

    def __init__(self):
        self._previous_state: dict[str, Any] | None = None
        self._previous_locations: dict[str, str] = {}
        self._previous_hazard: int = 0
        self._current_diff: WorldStateDiff = WorldStateDiff()

    def start_step(self, step: int, world_state: dict[str, Any]) -> None:
        """Call at the beginning of each step to snapshot the state"""
        self._current_diff = WorldStateDiff(step=step)

        # Track hazard level change
        current_hazard = world_state.get("hazard_level", 0)
        self._current_diff.hazard_level_delta = current_hazard - self._previous_hazard
        self._previous_hazard = current_hazard

    def record_movement(self, agent_id: str, from_loc: str, to_loc: str) -> None:
        """Record an agent movement"""
        self._current_diff.location_changes[agent_id] = (from_loc, to_loc)

    def record_event(self, event: str) -> None:
        """Record a new event"""
        self._current_diff.new_events.append(event)

    def record_hazard_change(self, description: str) -> None:
        """Record a hazard-related change"""
        self._current_diff.hazard_changes.append(description)

    def record_message(self) -> None:
        """Increment message counter"""
        self._current_diff.new_messages_count += 1

    def record_proposal(self) -> None:
        """Increment proposal counter"""
        self._current_diff.new_proposals_count += 1

    def record_trust_signal(self) -> None:
        """Increment trust signal counter"""
        self._current_diff.trust_signals_count += 1

    def get_current_diff(self) -> WorldStateDiff:
        """Get the diff for the current step"""
        return self._current_diff

    def end_step(self, world_state: dict[str, Any]) -> None:
        """Call at end of step to update previous state"""
        self._previous_state = world_state.copy()
        # Update previous locations
        agents = world_state.get("agents", {})
        self._previous_locations = {
            aid: info.get("location", "unknown")
            for aid, info in agents.items()
        }

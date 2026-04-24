"""Personality-modulated heartbeat scheduler for agent timing."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventTrigger(Enum):
    DIRECT_MESSAGE = "direct_message"
    HAZARD_AT_LOCATION = "hazard_at_location"
    NEGOTIATION_PROPOSAL = "negotiation_proposal"
    CONVERSATION_TURN = "conversation_turn"
    GOVERNANCE_RESPONSE = "governance_response"


@dataclass
class AgentHeartbeat:
    agent_id: str
    role: str
    base_interval: int
    next_beat_at: int
    frozen: bool = False
    stress_level: float = 50.0
    pending_triggers: list[EventTrigger] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "base_interval": self.base_interval,
            "next_beat_at": self.next_beat_at,
            "frozen": self.frozen,
            "stress_level": self.stress_level,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentHeartbeat:
        return cls(
            agent_id=data["agent_id"],
            role=data["role"],
            base_interval=data["base_interval"],
            next_beat_at=data["next_beat_at"],
            frozen=data.get("frozen", False),
            stress_level=data.get("stress_level", 50.0),
        )


class HeartbeatScheduler:
    def __init__(self) -> None:
        self._agents: dict[str, AgentHeartbeat] = {}

    def register(self, agent: Any) -> None:
        if agent.role != "human":
            base_interval = 1
        else:
            neuroticism = agent.persona.neuroticism
            conscientiousness = agent.persona.conscientiousness
            if neuroticism >= 7:
                base_interval = 1
            elif conscientiousness >= 7 and neuroticism <= 3:
                base_interval = 3
            else:
                base_interval = 2

        stress = 50.0
        if agent.role == "human" and hasattr(agent, "dynamic_state"):
            stress = agent.dynamic_state.get("stress_level", 50.0)

        self._agents[agent.id] = AgentHeartbeat(
            agent_id=agent.id,
            role=agent.role,
            base_interval=base_interval,
            next_beat_at=1,
            stress_level=stress,
        )

    def get_effective_interval(self, agent_id: str) -> int:
        hb = self._agents[agent_id]
        if hb.role != "human":
            return hb.base_interval

        stress = hb.stress_level
        if stress > 80:
            modifier = 0.5
        elif stress > 50:
            modifier = 0.75
        elif stress < 20:
            modifier = 1.5
        else:
            modifier = 1.0

        return max(1, math.floor(hb.base_interval * modifier))

    def get_ready_agents(self, step: int) -> dict[str, bool]:
        ready: dict[str, bool] = {}
        for agent_id, hb in self._agents.items():
            if hb.frozen:
                continue
            if step >= hb.next_beat_at or hb.pending_triggers:
                ready[agent_id] = True
                hb.pending_triggers.clear()
                hb.next_beat_at = step + self.get_effective_interval(agent_id)
        return ready

    def add_event_trigger(self, agent_id: str, trigger: EventTrigger) -> None:
        if agent_id in self._agents:
            self._agents[agent_id].pending_triggers.append(trigger)

    def freeze(self, agent_id: str) -> None:
        if agent_id in self._agents:
            self._agents[agent_id].frozen = True

    def unfreeze(self, agent_id: str) -> None:
        if agent_id in self._agents:
            self._agents[agent_id].frozen = False

    def update_stress(self, agent_id: str, stress_level: float) -> None:
        if agent_id in self._agents:
            self._agents[agent_id].stress_level = stress_level

    def to_dict(self) -> dict[str, Any]:
        return {
            agent_id: hb.to_dict()
            for agent_id, hb in self._agents.items()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HeartbeatScheduler:
        sched = cls()
        for agent_id, hb_data in data.items():
            sched._agents[agent_id] = AgentHeartbeat.from_dict(hb_data)
        return sched

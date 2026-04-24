"""SimulationEngineV2: heartbeat-scheduled, goal-aware, governance-gated engine."""

from __future__ import annotations

import logging
from typing import Any

from emotionsim.simulation.heartbeat import HeartbeatScheduler, EventTrigger
from emotionsim.simulation.goal_tree import GoalTree
from emotionsim.simulation.governance import GovernanceGate, GovernanceConfig
from emotionsim.core.config import get_settings

logger = logging.getLogger(__name__)


class SimulationEngineV2:
    """V2 engine with heartbeat scheduling, goal trees, and governance gates."""

    def __init__(self) -> None:
        settings = get_settings()

        self.heartbeat_scheduler = HeartbeatScheduler()
        self.goal_tree = GoalTree()

        gov_config = GovernanceConfig(
            threshold=settings.governance_threshold,
            timeout_seconds=settings.governance_timeout_seconds,
            timeout_action=settings.governance_timeout_action,
            use_llm_scorer=settings.governance_use_llm_scorer,
        )
        self.governance_gate = GovernanceGate(gov_config)

    def register_agents_v2(self, agents: dict[str, Any]) -> None:
        for agent in agents.values():
            self.heartbeat_scheduler.register(agent)

    def setup_mission(self, mission_goal: str, step: int = 0) -> None:
        self.goal_tree.set_mission(mission_goal, step=step)

    def get_ready_agent_ids(self, step: int) -> dict[str, bool]:
        return self.heartbeat_scheduler.get_ready_agents(step)

    def freeze_agent(self, agent_id: str) -> None:
        self.heartbeat_scheduler.freeze(agent_id)

    def unfreeze_agent(self, agent_id: str) -> None:
        self.heartbeat_scheduler.unfreeze(agent_id)

    def trigger_event(self, agent_id: str, trigger: EventTrigger) -> None:
        self.heartbeat_scheduler.add_event_trigger(agent_id, trigger)

    def update_agent_stress(self, agent_id: str, stress: float) -> None:
        self.heartbeat_scheduler.update_stress(agent_id, stress)

    def process_governance_resolutions(self) -> list[dict[str, Any]]:
        resolved = self.governance_gate.poll_resolutions()
        results = []
        for decision in resolved:
            self.unfreeze_agent(decision.agent_id)
            results.append({
                "agent_id": decision.agent_id,
                "approved": decision.approved,
                "action": decision.action,
                "researcher_note": decision.researcher_note,
                "decision_id": decision.id,
            })
        return results

    def update_goals_end_of_step(self, step: int) -> None:
        self.goal_tree.propagate_completions(step=step)

    def get_v2_state(self) -> dict[str, Any]:
        return {
            "heartbeat": self.heartbeat_scheduler.to_dict(),
            "goal_tree": self.goal_tree.to_dict(),
            "governance_audit": [d.to_dict() for d in self.governance_gate.get_audit_log()],
        }

"""Extended cognitive engine with goal alignment, governance, and goal updates."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

from app.agents.cognitive_engine import CognitiveEngine
from app.agents.intent_memory import IntentMemory, Plan
from app.agents.personality_mechanics import PersonalityMechanics
from app.simulation.goal_tree import GoalTree, GoalNode
from app.simulation.governance import GovernanceGate, GateStatus


LLMGenerateFn = Callable[..., Awaitable[Any]]


class CognitivePhaseV2(Enum):
    THINK = "think"
    ALIGN_GOALS = "align_goals"
    PLAN = "plan"
    GOVERNANCE_CHECK = "governance_check"
    ACT = "act"
    REFLECT = "reflect"
    UPDATE_GOALS = "update_goals"


@dataclass
class CycleResult:
    action: str | None = None
    reasoning: str | None = None
    governance_paused: bool = False
    governance_decision_id: str | None = None
    new_goals: list[dict[str, Any]] = field(default_factory=list)
    goal_updates: list[dict[str, Any]] = field(default_factory=list)
    selected_goal: GoalNode | None = None


class CognitiveEngineV2:
    def __init__(self, persona: Any) -> None:
        self._v1 = CognitiveEngine(persona)
        self._persona = persona
        self._mechanics = PersonalityMechanics(persona)

    def determine_phases(
        self,
        intent: IntentMemory,
        goal_tree: GoalTree,
        current_step: int,
    ) -> list[CognitivePhaseV2]:
        needs_full = (
            intent.current_plan is None
            or intent.plan_needs_replan(current_step)
            or intent.plan_deadline_exceeded(current_step)
        )
        if needs_full:
            return [
                CognitivePhaseV2.THINK,
                CognitivePhaseV2.ALIGN_GOALS,
                CognitivePhaseV2.PLAN,
                CognitivePhaseV2.GOVERNANCE_CHECK,
                CognitivePhaseV2.ACT,
                CognitivePhaseV2.REFLECT,
                CognitivePhaseV2.UPDATE_GOALS,
            ]
        return [
            CognitivePhaseV2.GOVERNANCE_CHECK,
            CognitivePhaseV2.ACT,
            CognitivePhaseV2.REFLECT,
            CognitivePhaseV2.UPDATE_GOALS,
        ]

    def align_goals(
        self,
        agent_id: str,
        goal_tree: GoalTree,
    ) -> dict[str, Any]:
        top_goal = goal_tree.get_highest_priority_goal(agent_id)
        goal_context = goal_tree.get_context_string(agent_id)

        needs_new = top_goal is None
        ancestry: list[str] = []
        if top_goal:
            ancestry = [g.description for g in goal_tree.get_ancestry(top_goal.id)]

        return {
            "selected_goal": top_goal,
            "goal_context": goal_context,
            "goal_ancestry": ancestry,
            "needs_new_goal": needs_new,
        }

    def governance_check(
        self,
        agent_id: str,
        action: str,
        reasoning: str,
        step: int,
        gate: GovernanceGate | None,
    ) -> dict[str, Any]:
        if gate is None:
            return {"passed": True, "paused": False, "decision_id": None}

        decision = gate.evaluate(
            agent_id=agent_id,
            action=action,
            reasoning=reasoning,
            step=step,
        )

        if decision.status == GateStatus.PASSED:
            return {"passed": True, "paused": False, "decision_id": None}

        return {
            "passed": False,
            "paused": True,
            "decision_id": decision.id,
        }

    def update_goals(
        self,
        goal_tree: GoalTree,
        step: int,
    ) -> None:
        goal_tree.propagate_completions(step=step)

    async def think(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return await self._v1.think(*args, **kwargs)

    async def plan(self, *args: Any, **kwargs: Any) -> Plan:
        return await self._v1.plan(*args, **kwargs)

    def reflect(self, *args: Any, **kwargs: Any) -> None:
        return self._v1.reflect(*args, **kwargs)

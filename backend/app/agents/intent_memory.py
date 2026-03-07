"""Intent memory system (Tier 4) - plans, commitments, blocked actions"""
from typing import Any
from dataclasses import dataclass, field


@dataclass
class Plan:
    """A plan the agent is currently pursuing"""
    goal: str
    steps: list[str]
    current_step: int
    created_at_step: int
    success_criteria: str
    fallback: str | None
    deadline_step: int | None
    retry_count: int
    goal_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": self.steps,
            "current_step": self.current_step,
            "created_at_step": self.created_at_step,
            "success_criteria": self.success_criteria,
            "fallback": self.fallback,
            "deadline_step": self.deadline_step,
            "retry_count": self.retry_count,
            "goal_id": self.goal_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Plan":
        return cls(**data)


@dataclass
class Commitment:
    """A promise made to another agent"""
    to: str
    what: str
    step: int

    def to_dict(self) -> dict[str, Any]:
        return {"to": self.to, "what": self.what, "step": self.step}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Commitment":
        return cls(**data)


@dataclass
class BlockedAction:
    """An action that previously failed"""
    action: str
    reason: str
    step: int

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "reason": self.reason, "step": self.step}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BlockedAction":
        return cls(**data)


@dataclass
class CompletedPlan:
    """A plan that has been completed, failed, or abandoned"""
    goal: str
    outcome: str  # "success", "failed", "abandoned"
    reason: str
    steps_taken: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "outcome": self.outcome,
            "reason": self.reason,
            "steps_taken": self.steps_taken,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompletedPlan":
        return cls(**data)


class IntentMemory:
    """
    Tier 4 memory: tracks agent plans, commitments, and blocked actions.

    Provides the cognitive layer with awareness of what the agent is trying
    to do, what it has promised others, and what has failed before.
    """

    def __init__(self) -> None:
        self.current_plan: Plan | None = None
        self.commitments: list[Commitment] = []
        self.completed_plans: list[CompletedPlan] = []
        self.blocked_actions: list[BlockedAction] = []

    def set_plan(self, plan: Plan) -> None:
        """Set or replace the current plan."""
        self.current_plan = plan

    def advance_plan_step(self) -> None:
        """Increment current_step on the active plan."""
        if self.current_plan is not None:
            self.current_plan.current_step += 1

    def complete_plan(self, outcome: str, reason: str) -> None:
        """Move current plan to completed_plans and clear it."""
        if self.current_plan is None:
            return
        completed = CompletedPlan(
            goal=self.current_plan.goal,
            outcome=outcome,
            reason=reason,
            steps_taken=self.current_plan.current_step,
        )
        self.completed_plans.append(completed)
        # Cap at 5 most recent
        if len(self.completed_plans) > 5:
            self.completed_plans = self.completed_plans[-5:]
        self.current_plan = None

    def add_commitment(self, to: str, what: str, step: int) -> None:
        """Record a promise made to another agent."""
        self.commitments.append(Commitment(to=to, what=what, step=step))
        if len(self.commitments) > 10:
            self.commitments = self.commitments[-10:]

    def add_blocked_action(self, action: str, reason: str, step: int) -> None:
        """Record an action that failed."""
        self.blocked_actions.append(BlockedAction(action=action, reason=reason, step=step))
        if len(self.blocked_actions) > 20:
            self.blocked_actions = self.blocked_actions[-20:]

    def is_action_blocked(self, action: str) -> bool:
        """Check if an action has previously failed."""
        return any(ba.action == action for ba in self.blocked_actions)

    def plan_needs_replan(self, current_step: int) -> bool:
        """True if there is no viable plan: no plan, retries exhausted, or plan complete."""
        if self.current_plan is None:
            return True
        if self.current_plan.retry_count >= 3:
            return True
        if self.current_plan.current_step >= len(self.current_plan.steps):
            return True
        return False

    def plan_deadline_exceeded(self, current_step: int) -> bool:
        """True if the current plan has passed its deadline."""
        if self.current_plan is None:
            return False
        if self.current_plan.deadline_step is None:
            return False
        return current_step >= self.current_plan.deadline_step

    def get_context_string(self) -> str:
        """Render plan, commitments, and blocked actions for prompt inclusion."""
        parts: list[str] = []

        if self.current_plan:
            p = self.current_plan
            parts.append(f"\nCurrent plan: {p.goal}")
            parts.append(f"  Success criteria: {p.success_criteria}")
            if p.fallback:
                parts.append(f"  Fallback: {p.fallback}")
            if p.deadline_step is not None:
                parts.append(f"  Deadline: step {p.deadline_step}")
            parts.append("  Steps:")
            for i, step in enumerate(p.steps):
                marker = ">>>" if i == p.current_step else "   "
                done = "[done]" if i < p.current_step else "[    ]"
                parts.append(f"    {marker} {done} {step}")

        if self.commitments:
            parts.append("\nCommitments:")
            for c in self.commitments:
                parts.append(f"  - Promised {c.to}: {c.what} (step {c.step})")

        if self.blocked_actions:
            parts.append("\nBlocked actions (tried and failed):")
            for ba in self.blocked_actions:
                parts.append(f"  - {ba.action}: {ba.reason}")

        if self.completed_plans:
            parts.append("\nRecent plan outcomes:")
            for cp in self.completed_plans[-3:]:
                parts.append(f"  - {cp.goal}: {cp.outcome} ({cp.reason})")

        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "current_plan": self.current_plan.to_dict() if self.current_plan else None,
            "commitments": [c.to_dict() for c in self.commitments],
            "completed_plans": [cp.to_dict() for cp in self.completed_plans],
            "blocked_actions": [ba.to_dict() for ba in self.blocked_actions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentMemory":
        """Restore from dictionary."""
        im = cls()
        plan_data = data.get("current_plan")
        if plan_data is not None:
            im.current_plan = Plan.from_dict(plan_data)
        im.commitments = [
            Commitment.from_dict(c) for c in data.get("commitments", [])
        ]
        im.completed_plans = [
            CompletedPlan.from_dict(cp) for cp in data.get("completed_plans", [])
        ]
        im.blocked_actions = [
            BlockedAction.from_dict(ba) for ba in data.get("blocked_actions", [])
        ]
        return im

    def clear(self) -> None:
        """Reset all intent memory."""
        self.current_plan = None
        self.commitments.clear()
        self.completed_plans.clear()
        self.blocked_actions.clear()

"""Hierarchical goal tree: mission -> group -> individual goals."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GoalLevel(Enum):
    MISSION = "mission"
    GROUP = "group"
    INDIVIDUAL = "individual"


class GoalStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


@dataclass
class GoalNode:
    description: str
    level: GoalLevel
    owner_ids: list[str]
    created_at_step: int
    id: str = ""
    parent_id: str | None = None
    status: GoalStatus = GoalStatus.ACTIVE
    priority: int = 5
    alignment_score: float = 1.0
    conflict_with: list[str] = field(default_factory=list)
    completed_at_step: int | None = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())[:8]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "level": self.level.value,
            "parent_id": self.parent_id,
            "owner_ids": self.owner_ids,
            "status": self.status.value,
            "priority": self.priority,
            "created_at_step": self.created_at_step,
            "completed_at_step": self.completed_at_step,
            "alignment_score": self.alignment_score,
            "conflict_with": self.conflict_with,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoalNode:
        return cls(
            id=data["id"],
            description=data["description"],
            level=GoalLevel(data["level"]),
            parent_id=data.get("parent_id"),
            owner_ids=data["owner_ids"],
            status=GoalStatus(data.get("status", "active")),
            priority=data.get("priority", 5),
            created_at_step=data["created_at_step"],
            completed_at_step=data.get("completed_at_step"),
            alignment_score=data.get("alignment_score", 1.0),
            conflict_with=data.get("conflict_with", []),
        )


class GoalTree:
    def __init__(self) -> None:
        self._goals: dict[str, GoalNode] = {}
        self.mission: GoalNode | None = None

    def set_mission(self, description: str, step: int) -> str:
        node = GoalNode(
            description=description,
            level=GoalLevel.MISSION,
            owner_ids=[],
            created_at_step=step,
        )
        self._goals[node.id] = node
        self.mission = node
        return node.id

    def add_group_goal(self, description: str, owner_ids: list[str],
                       step: int, priority: int = 5) -> str:
        node = GoalNode(
            description=description,
            level=GoalLevel.GROUP,
            parent_id=self.mission.id if self.mission else None,
            owner_ids=owner_ids,
            created_at_step=step,
            priority=priority,
        )
        self._goals[node.id] = node
        return node.id

    def add_agent_goal(self, description: str, owner_id: str,
                       parent_id: str, step: int, priority: int = 5) -> str:
        node = GoalNode(
            description=description,
            level=GoalLevel.INDIVIDUAL,
            parent_id=parent_id,
            owner_ids=[owner_id],
            created_at_step=step,
            priority=priority,
        )
        self._goals[node.id] = node
        return node.id

    def get_goal(self, goal_id: str) -> GoalNode:
        return self._goals[goal_id]

    def get_agent_goals(self, agent_id: str) -> list[GoalNode]:
        return [
            g for g in self._goals.values()
            if agent_id in g.owner_ids and g.level == GoalLevel.INDIVIDUAL
        ]

    def get_active_goals(self, agent_id: str) -> list[GoalNode]:
        return [
            g for g in self.get_agent_goals(agent_id)
            if g.status == GoalStatus.ACTIVE
        ]

    def get_highest_priority_goal(self, agent_id: str) -> GoalNode | None:
        active = self.get_active_goals(agent_id)
        if not active:
            return None
        return max(active, key=lambda g: g.priority)

    def get_ancestry(self, goal_id: str) -> list[GoalNode]:
        chain: list[GoalNode] = []
        current = self._goals.get(goal_id)
        while current:
            chain.append(current)
            current = self._goals.get(current.parent_id) if current.parent_id else None
        chain.reverse()
        return chain

    def complete_goal(self, goal_id: str, step: int) -> None:
        self._goals[goal_id].status = GoalStatus.COMPLETED
        self._goals[goal_id].completed_at_step = step

    def fail_goal(self, goal_id: str, step: int) -> None:
        self._goals[goal_id].status = GoalStatus.FAILED
        self._goals[goal_id].completed_at_step = step

    def abandon_goal(self, goal_id: str, step: int) -> None:
        self._goals[goal_id].status = GoalStatus.ABANDONED
        self._goals[goal_id].completed_at_step = step

    def set_alignment(self, goal_id: str, score: float) -> None:
        self._goals[goal_id].alignment_score = score

    def add_conflict(self, goal_a_id: str, goal_b_id: str) -> None:
        a = self._goals[goal_a_id]
        b = self._goals[goal_b_id]
        if goal_b_id not in a.conflict_with:
            a.conflict_with.append(goal_b_id)
        if goal_a_id not in b.conflict_with:
            b.conflict_with.append(goal_a_id)

    def propagate_completions(self, step: int) -> None:
        for goal in list(self._goals.values()):
            if goal.level != GoalLevel.GROUP or goal.status != GoalStatus.ACTIVE:
                continue
            children = [
                g for g in self._goals.values()
                if g.parent_id == goal.id
            ]
            if children and all(c.status == GoalStatus.COMPLETED for c in children):
                goal.status = GoalStatus.COMPLETED
                goal.completed_at_step = step

    def get_context_string(self, agent_id: str) -> str:
        lines: list[str] = []
        if self.mission:
            lines.append(f"MISSION: {self.mission.description}")
        for g in self._goals.values():
            if g.level != GoalLevel.GROUP or g.status != GoalStatus.ACTIVE:
                continue
            agent_children = [
                c for c in self._goals.values()
                if c.parent_id == g.id and agent_id in c.owner_ids
            ]
            if agent_children or agent_id in g.owner_ids:
                lines.append(f"  GROUP GOAL: {g.description}")
                for c in agent_children:
                    status = "ACTIVE" if c.status == GoalStatus.ACTIVE else c.status.value
                    lines.append(f"    YOUR GOAL [{status}] (priority {c.priority}): {c.description}")
                    if c.conflict_with:
                        lines.append(f"      CONFLICTS WITH: {len(c.conflict_with)} other goal(s)")
                    if c.alignment_score < 0:
                        lines.append(f"      WARNING: This goal may conflict with the group goal (alignment: {c.alignment_score:.1f})")
        return "\n".join(lines) if lines else "No goals assigned."

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission.id if self.mission else None,
            "goals": {gid: g.to_dict() for gid, g in self._goals.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoalTree:
        tree = cls()
        for gid, gdata in data["goals"].items():
            node = GoalNode.from_dict(gdata)
            tree._goals[gid] = node
        mission_id = data.get("mission_id")
        if mission_id and mission_id in tree._goals:
            tree.mission = tree._goals[mission_id]
        return tree

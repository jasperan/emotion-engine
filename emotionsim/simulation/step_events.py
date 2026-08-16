"""Step-event payload builders (Step 7 refactor).

Moves the step_completed event payload construction out of the engine
monolith into a testable helper.
"""

from __future__ import annotations

from typing import Any


def build_step_completed_payload(
    step: int,
    actions: list[dict[str, Any]],
    messages: list[dict[str, Any]],
    world_state: dict[str, Any],
    conversations: list[dict[str, Any]],
    agent_telemetry: dict[str, dict[str, Any]],
    world_state_diff: dict[str, Any],
    negotiations: dict[str, Any],
    emotion_contagion: dict[str, Any],
    social_dynamics: dict[str, Any],
    governance_pending: list[dict[str, Any]] | None = None,
    goal_tree: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the payload emitted on each ``step_completed`` event."""
    payload: dict[str, Any] = {
        "step": step,
        "actions": actions,
        "messages": messages,
        "world_state": world_state,
        "conversations": conversations,
        "agent_telemetry": agent_telemetry,
        "world_state_diff": world_state_diff,
        "negotiations": negotiations,
        "emotion_contagion": emotion_contagion,
        "social_dynamics": social_dynamics,
    }
    if governance_pending is not None:
        payload["governance_pending"] = governance_pending
    if goal_tree is not None:
        payload["goal_tree"] = goal_tree
    return payload

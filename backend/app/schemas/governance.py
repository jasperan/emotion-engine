"""Pydantic models for governance gate API events."""

from __future__ import annotations

from pydantic import BaseModel


class GateEventResponse(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    action: str
    reasoning: str
    significance_score: float
    categories: list[str]
    affected_agents: list[str]
    goal_ancestry: list[str]
    step: int

    model_config = {"from_attributes": True}


class GateResolutionRequest(BaseModel):
    decision_id: str
    approved: bool
    researcher_note: str = ""


class GovernanceConfigUpdate(BaseModel):
    threshold: float | None = None
    active_categories: list[str] | None = None
    timeout_seconds: float | None = None
    timeout_action: str | None = None

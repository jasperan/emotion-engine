"""Run-related Pydantic schemas"""
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    """Schema for creating a run"""
    scenario_id: str
    seed: int | None = None
    max_steps: int | None = None  # Override scenario default


class RunResponse(BaseModel):
    """Schema for run API responses"""
    id: str
    scenario_id: str
    status: str
    current_step: int
    max_steps: int
    seed: int | None
    world_state: dict[str, Any]
    metrics: dict[str, Any]
    evaluation: dict[str, Any]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    
    class Config:
        from_attributes = True


class RunControl(BaseModel):
    """Schema for run control commands"""
    action: Literal["start", "pause", "resume", "stop", "step"]


class StepResponse(BaseModel):
    """Schema for step API responses"""
    id: str
    run_id: str
    step_index: int
    state_snapshot: dict[str, Any]
    actions: list[dict[str, Any]]
    step_metrics: dict[str, Any]
    timestamp: datetime
    
    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Schema for message API responses"""
    id: str
    run_id: str
    from_agent_id: str | None
    to_target: str
    message_type: str
    content: str
    metadata: dict[str, Any] = Field(validation_alias='msg_metadata')
    step_index: int
    timestamp: datetime
    
    class Config:
        from_attributes = True


class WebSocketEvent(BaseModel):
    """Event sent over WebSocket"""
    event_type: Literal["step", "message", "agent_action", "state_change", "run_status", "error"]
    data: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


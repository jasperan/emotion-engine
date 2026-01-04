"""Scenario-related Pydantic schemas"""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

from app.schemas.agent import AgentConfig


class WorldConfig(BaseModel):
    """World configuration for a scenario"""
    name: str = Field(..., description="World/environment name")
    description: str = Field("", description="World description")
    
    # Environment parameters
    initial_state: dict[str, Any] = Field(default_factory=dict, description="Initial world state")
    dynamics: dict[str, Any] = Field(default_factory=dict, description="How the world changes over time")
    
    # Simulation settings
    max_steps: int | None = Field(None, ge=1, le=10000, description="Maximum simulation steps (None = infinite until consensus)")
    tick_delay: float = Field(0.5, ge=0, le=60, description="Delay between ticks in seconds")


class ScenarioCreate(BaseModel):
    """Schema for creating a scenario"""
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field("")
    config: WorldConfig
    agent_templates: list[AgentConfig] = Field(default_factory=list)


class ScenarioUpdate(BaseModel):
    """Schema for updating a scenario"""
    name: str | None = None
    description: str | None = None
    config: WorldConfig | None = None
    agent_templates: list[AgentConfig] | None = None


class ScenarioResponse(BaseModel):
    """Schema for scenario API responses"""
    id: str
    name: str
    description: str
    config: dict[str, Any]
    agent_templates: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


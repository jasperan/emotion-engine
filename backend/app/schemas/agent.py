"""Agent-related Pydantic schemas"""
from typing import Any, Literal
from pydantic import BaseModel, Field

from app.schemas.persona import Persona


class AgentAction(BaseModel):
    """An action taken by an agent"""
    action_type: str = Field(..., description="Type of action (move, speak, help, etc.)")
    target: str | None = Field(None, description="Target of the action (agent, location, item)")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Action-specific parameters")


class AgentMessage(BaseModel):
    """A message sent by an agent"""
    content: str = Field(..., description="Message content")
    to_target: str = Field(..., description="Target agent ID, room name, or 'broadcast'")
    message_type: Literal["direct", "room", "broadcast"] = Field("direct")


class AgentResponse(BaseModel):
    """Response from an agent's tick() method"""
    actions: list[AgentAction] = Field(default_factory=list, description="Actions to perform")
    message: AgentMessage | None = Field(None, description="Optional message to send")
    state_changes: dict[str, Any] = Field(default_factory=dict, description="Changes to agent's dynamic state")
    reasoning: str = Field("", description="Agent's internal reasoning (for logging)")


class AgentConfig(BaseModel):
    """Configuration for creating an agent"""
    name: str
    role: Literal["environment", "human", "designer", "evaluator"]
    model_id: str = "llama3.2"
    provider: Literal["ollama", "anthropic"] = "ollama"
    persona: Persona | None = None  # Required for human agents
    goals: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    initial_state: dict[str, Any] = Field(default_factory=dict)


class AgentStatus(BaseModel):
    """Current status of an agent in a run"""
    id: str
    name: str
    role: str
    is_active: bool
    persona: Persona | None = None
    dynamic_state: dict[str, Any] = Field(default_factory=dict)


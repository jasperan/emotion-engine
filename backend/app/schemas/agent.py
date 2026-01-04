"""Agent-related Pydantic schemas"""
from typing import Any, Literal
from pydantic import BaseModel, Field

from app.schemas.persona import Persona



from app.schemas.item import Item

class AgentAction(BaseModel):
    """An action taken by an agent"""
    action_type: Literal[
        "move", "speak", "wait", "reflect", 
        "search", "take", "drop", "use", "interact",
        "propose_task", "accept_task", "report_progress", "call_for_vote"
    ] = Field(..., description="Type of action")
    target: str | None = Field(None, description="Target of the action (agent, location, item)")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Action-specific parameters")


class AgentMessage(BaseModel):
    """A message sent by an agent"""
    content: str = Field(..., description="Message content")
    to_target: str = Field(..., description="Target agent ID, room name, or 'broadcast'")
    message_type: Literal["direct", "room", "broadcast"] = Field("direct")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional metadata (e.g. context size)")


class AgentResponse(BaseModel):
    """Response from an agent's tick() method"""
    actions: list[AgentAction] = Field(default_factory=list, description="Actions to perform")
    message: AgentMessage | None = Field(None, description="Optional message to send")
    state_changes: dict[str, Any] = Field(default_factory=dict, description="Changes to agent's dynamic state")
    reasoning: str = Field("", description="Agent's internal reasoning (for logging)")


class AgentConfig(BaseModel):
    """Configuration for creating an agent"""
    model_config = {'protected_namespaces': ()}
    name: str
    role: Literal["environment", "human", "designer", "evaluator"]
    model_id: str = "phi3"
    provider: Literal["ollama", "anthropic"] = "ollama"
    persona: Persona | None = None  # Required for human agents
    goals: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    initial_state: dict[str, Any] = Field(default_factory=dict)
    inventory: list[Item] = Field(default_factory=list, description="Initial inventory")


class AgentStatus(BaseModel):
    """Current status of an agent in a run"""
    id: str
    name: str
    role: str
    is_active: bool
    persona: Persona | None = None
    dynamic_state: dict[str, Any] = Field(default_factory=dict)
    inventory: list[Item] = Field(default_factory=list)



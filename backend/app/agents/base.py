"""Base Agent class"""
import json
import uuid
from abc import ABC, abstractmethod
from typing import Any

from app.llm.base import LLMMessage, LLMResponse
from app.llm.router import LLMRouter
from app.schemas.agent import AgentResponse, AgentAction, AgentMessage
from app.agents.memory import AgentMemory


class Agent(ABC):
    """Base class for all agents in the simulation"""
    
    def __init__(
        self,
        agent_id: str | None = None,
        name: str = "Agent",
        role: str = "base",
        model_id: str = "phi3",
        provider: str = "ollama",
        goals: list[str] | None = None,
        tools: list[str] | None = None,
        memory_limit: int = 50,
    ):
        self.id = agent_id or str(uuid.uuid4())
        self.name = name
        self.role = role
        self.model_id = model_id
        self.provider = provider
        self.goals = goals or []
        self.tools = tools or []
        
        # Enhanced memory system
        self.agent_memory = AgentMemory(
            agent_id=self.id,
            agent_name=self.name,
            sliding_window_size=memory_limit,
        )
        
        # Legacy memory list for backwards compatibility
        self.memory: list[dict[str, Any]] = []
        self.memory_limit = memory_limit
        
        # Dynamic state
        self.dynamic_state: dict[str, Any] = {}
        
        # LLM client
        self._llm_client = LLMRouter.get_client(provider)  # type: ignore
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Generate the system prompt for this agent"""
        pass
    
    @abstractmethod
    def build_context(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> str:
        """Build the context/user prompt from world state and messages"""
        pass
    
    def add_to_memory(self, event: dict[str, Any]) -> None:
        """Add an event to memory, maintaining the limit"""
        # Add to legacy memory list
        self.memory.append(event)
        if len(self.memory) > self.memory_limit:
            self.memory = self.memory[-self.memory_limit:]
        
        # Add to enhanced memory system
        self.agent_memory.add_event(event)
    
    def get_conversation_context(self) -> str:
        """Get conversation context from memory including relationships and episodic memories"""
        return self.agent_memory.get_conversation_context()
    
    def get_relationship_context(self, agent_ids: list[str]) -> str:
        """Get relationship context for specific agents"""
        context_parts = []
        
        for agent_id in agent_ids:
            rel = self.agent_memory.get_relationship(agent_id)
            if rel:
                trust_desc = (
                    "I trust them" if rel.trust_level >= 7
                    else "I'm familiar with them" if rel.trust_level >= 4
                    else "I'm uncertain about them"
                )
                context_parts.append(
                    f"- {rel.agent_name}: {trust_desc}. "
                    f"We've had {rel.interaction_count} interactions. "
                    f"My feeling toward them is {rel.sentiment}."
                )
                if rel.notes:
                    context_parts.append(f"  Note: {rel.notes[-1]}")
        
        return "\n".join(context_parts)
    
    def update_arrival_context(
        self,
        location: str,
        from_location: str | None,
        reason: str,
        step_index: int,
    ) -> None:
        """Update the context of how agent arrived at current location"""
        self.agent_memory.set_arrival_context(
            location=location,
            from_location=from_location,
            reason=reason,
            step_index=step_index,
        )
    
    def parse_llm_response(self, response: LLMResponse) -> AgentResponse:
        """Parse LLM response into structured AgentResponse"""
        content = response.content.strip()
        
        # Try to parse as JSON first
        try:
            data = json.loads(content)
            actions = []
            for action_data in data.get("actions", []):
                actions.append(AgentAction(
                    action_type=action_data.get("action_type", "none"),
                    target=action_data.get("target"),
                    parameters=action_data.get("parameters", {}),
                ))
            
            message = None
            if data.get("message"):
                msg_data = data["message"]
                message = AgentMessage(
                    content=msg_data.get("content", ""),
                    to_target=msg_data.get("to_target", "broadcast"),
                    message_type=msg_data.get("message_type", "broadcast"),
                )
            
            return AgentResponse(
                actions=actions,
                message=message,
                state_changes=data.get("state_changes", {}),
                reasoning=data.get("reasoning", ""),
            )
        except json.JSONDecodeError:
            # If not JSON, treat as a simple message response
            return AgentResponse(
                actions=[],
                message=AgentMessage(
                    content=content,
                    to_target="broadcast",
                    message_type="broadcast",
                ),
                state_changes={},
                reasoning="",
            )
    
    async def tick(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> AgentResponse:
        """
        Execute one simulation tick.
        
        Args:
            world_state: Current state of the world/environment
            messages: Recent messages addressed to this agent
            
        Returns:
            AgentResponse with actions and optional message
        """
        # Store incoming messages in memory
        for msg in messages:
            self.add_to_memory({"type": "message", "data": msg})
        
        # Build prompts
        system_prompt = self.get_system_prompt()
        context = self.build_context(world_state, messages)
        
        # Call LLM
        llm_messages = [LLMMessage(role="user", content=context)]
        
        response = await self._llm_client.generate(
            messages=llm_messages,
            model=self.model_id,
            system=system_prompt,
            temperature=0.7,
            json_mode=True,
        )
        
        # Parse and return response
        agent_response = self.parse_llm_response(response)
        
        # Apply state changes
        self.dynamic_state.update(agent_response.state_changes)
        
        # Store our action in memory
        self.add_to_memory({
            "type": "action",
            "actions": [a.model_dump() for a in agent_response.actions],
            "message": agent_response.message.model_dump() if agent_response.message else None,
        })
        
        return agent_response
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize agent to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "model_id": self.model_id,
            "provider": self.provider,
            "goals": self.goals,
            "tools": self.tools,
            "dynamic_state": self.dynamic_state,
            "memory": self.agent_memory.to_dict(),
        }
    
    def restore_memory(self, memory_data: dict[str, Any]) -> None:
        """Restore memory from serialized data"""
        self.agent_memory = AgentMemory.from_dict(memory_data)

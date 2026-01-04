"""Base Agent class"""
import json
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable, Awaitable

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
        model_id: str = "gemma3:270m",
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
        
        self.memory_limit = memory_limit
        
        # Dynamic state
        self.dynamic_state: dict[str, Any] = {}
        self.inventory = [] # Initialize empty inventory

        
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
        step_actions: list[dict[str, Any]] | None = None,
        step_messages: list[dict[str, Any]] | None = None,
        step_events: list[str] | None = None,
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
        
        # Try to extract JSON from various formats
        json_content = self._extract_json(content)
        
        if json_content:
            try:
                data = json.loads(json_content)
                return self._parse_json_response(data)
            except json.JSONDecodeError:
                pass
        
        # Fallback: treat as natural language response
        # Clean up any JSON-like artifacts
        clean_content = self._clean_response_text(content)
        
        return AgentResponse(
            actions=[],
            message=AgentMessage(
                content=clean_content,
                to_target="broadcast",
                message_type="broadcast",
            ) if clean_content else None,
            state_changes={},
            reasoning="",
        )
    
    def _extract_json(self, content: str) -> str | None:
        """Extract JSON from response, handling various formats"""
        import re
        
        # Already valid JSON?
        if content.startswith("{") and content.endswith("}"):
            return content
        
        # Extract from markdown code blocks
        json_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if json_block:
            return json_block.group(1).strip()
        
        # Find JSON object in text
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        return None
    
    def _parse_json_response(self, data: dict) -> AgentResponse:
        """Parse a JSON dict into AgentResponse"""
        actions = []
        for action_data in data.get("actions", []):
            if isinstance(action_data, dict):
                # Coerce target to string or None to handle LLM returning non-string values
                target_raw = action_data.get("target")
                if target_raw is None:
                    target = None
                elif isinstance(target_raw, str):
                    target = target_raw.strip() if target_raw.strip() else None
                else:
                    # Convert non-string values to string (e.g., numbers, booleans)
                    target = str(target_raw) if target_raw else None
                
                actions.append(AgentAction(
                    action_type=action_data.get("action_type", "none"),
                    target=target,
                    parameters=action_data.get("parameters", {}),
                ))
        
        message = None
        msg_data = data.get("message")
        if msg_data:
            if isinstance(msg_data, dict):
                msg_content = msg_data.get("content", "")
                # Don't use JSON-looking content as message
                if msg_content and not msg_content.strip().startswith("{"):
                    # Validate message_type - must be one of the allowed values
                    msg_type = msg_data.get("message_type", "broadcast")
                    valid_types = ("direct", "room", "broadcast")
                    if msg_type not in valid_types:
                        msg_type = "broadcast"
                    
                    # Validate to_target - must be a non-empty string
                    to_target = msg_data.get("to_target", "broadcast")
                    if not to_target or not isinstance(to_target, str):
                        to_target = "broadcast"
                    
                    message = AgentMessage(
                        content=msg_content,
                        to_target=to_target,
                        message_type=msg_type,
                    )
            elif isinstance(msg_data, str) and not msg_data.strip().startswith("{"):
                message = AgentMessage(
                    content=msg_data,
                    to_target="broadcast",
                    message_type="broadcast",
                )
        
        return AgentResponse(
            actions=actions,
            message=message,
            state_changes=data.get("state_changes", {}),
            reasoning=data.get("reasoning", ""),
        )
    
    def _clean_response_text(self, content: str) -> str:
        """Clean up response text, removing JSON artifacts"""
        import re
        
        # If it looks like JSON, don't use it as a message
        if content.strip().startswith("{") or content.strip().startswith("["):
            # Try to extract a "content" field from partial JSON
            content_match = re.search(r'"content"\s*:\s*"([^"]+)"', content)
            if content_match:
                return content_match.group(1)
            return ""
        
        # Remove any JSON blocks
        content = re.sub(r'```(?:json)?\s*\n?.*?\n?```', '', content, flags=re.DOTALL)
        
        # Clean up
        content = content.strip()
        
        return content
    
    async def tick(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
        step_actions: list[dict[str, Any]] | None = None,
        step_messages: list[dict[str, Any]] | None = None,
        step_events: list[str] | None = None,
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> AgentResponse:
        """
        Execute one simulation tick.
        
        Args:
            world_state: Current state of the world/environment
            messages: Recent messages addressed to this agent
            step_actions: Actions taken by other agents in current step
            step_messages: Messages sent by other agents in current step
            step_events: Events that occurred in current step
            stream_callback: Async callback for streaming tokens
            
        Returns:
            AgentResponse with actions and optional message
        """
        # Store incoming messages in memory
        for msg in messages:
            self.add_to_memory({"type": "message", "data": msg})
        
        # Build prompts
        system_prompt = self.get_system_prompt()
        context = self.build_context(world_state, messages, step_actions, step_messages, step_events)
        
        # Call LLM with increased token limit for complete responses
        llm_messages = [LLMMessage(role="user", content=context)]
        context_size = len(context)
        
        response = await self._llm_client.generate(
            messages=llm_messages,
            model=self.model_id,
            system=system_prompt,
            temperature=0.8,  # Increased for more creative responses
            max_tokens=8192,  # Increased to prevent truncated sentences
            json_mode=True,
            stream_callback=stream_callback,
        )
        
        # Parse and return response
        agent_response = self.parse_llm_response(response)
        
        # Add context size to message metadata if message exists
        if agent_response.message:
            if not agent_response.message.metadata:
                agent_response.message.metadata = {}
            agent_response.message.metadata["context_size"] = context_size
        
        # Apply state changes
        self.dynamic_state.update(agent_response.state_changes)
        
        # Store our action in memory
        self.add_to_memory({
            "type": "action",
            "actions": [a.model_dump() for a in agent_response.actions],
            "message": agent_response.message.model_dump() if agent_response.message else None,
            "context_size": context_size,
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
            "inventory": [item.model_dump() for item in self.inventory],
            "memory": self.agent_memory.to_dict(),
        }
    
    def restore_memory(self, memory_data: dict[str, Any]) -> None:
        """Restore memory from serialized data"""
        self.agent_memory = AgentMemory.from_dict(memory_data)

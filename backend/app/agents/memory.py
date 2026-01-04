"""Agent memory system with sliding window and episodic memory"""
from typing import Any
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class EpisodicMemory:
    """A summarized memory of a significant event or conversation"""
    id: str
    summary: str
    participants: list[str]
    location: str | None
    step_range: tuple[int, int]  # (start_step, end_step)
    emotional_impact: str  # positive, negative, neutral
    importance: int  # 1-10 scale
    key_facts: list[str]
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "summary": self.summary,
            "participants": self.participants,
            "location": self.location,
            "step_range": self.step_range,
            "emotional_impact": self.emotional_impact,
            "importance": self.importance,
            "key_facts": self.key_facts,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EpisodicMemory":
        data = data.copy()
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "step_range" in data and isinstance(data["step_range"], list):
            data["step_range"] = tuple(data["step_range"])
        return cls(**data)


@dataclass
class RelationshipMemory:
    """Memory of relationship with another agent"""
    agent_id: str
    agent_name: str
    first_met_step: int
    first_met_location: str | None
    interaction_count: int = 0
    trust_level: int = 5  # 1-10 scale
    last_interaction_step: int = 0
    sentiment: str = "neutral"  # positive, negative, neutral
    notes: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "first_met_step": self.first_met_step,
            "first_met_location": self.first_met_location,
            "interaction_count": self.interaction_count,
            "trust_level": self.trust_level,
            "last_interaction_step": self.last_interaction_step,
            "sentiment": self.sentiment,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RelationshipMemory":
        return cls(**data)


class AgentMemory:
    """
    Comprehensive memory system for agents.
    
    Features:
    - Sliding window of recent messages/events
    - Episodic memory for significant events with summaries
    - Relationship memory for tracking interactions with other agents
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        sliding_window_size: int = 50,
        summarize_threshold: int = 30,  # Summarize when this many messages accumulate
    ):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.sliding_window_size = sliding_window_size
        self.summarize_threshold = summarize_threshold
        
        # Recent messages/events (sliding window)
        self._recent_events: list[dict[str, Any]] = []
        
        # Episodic memories (summarized significant events)
        self._episodic_memories: list[EpisodicMemory] = []
        self._episodic_counter: int = 0
        
        # Relationship memories
        self._relationships: dict[str, RelationshipMemory] = {}
        
        # Events pending summarization
        self._pending_summarization: list[dict[str, Any]] = []
        
        # How the agent arrived at current location
        self._arrival_context: dict[str, Any] = {}
    
    def add_event(self, event: dict[str, Any]) -> None:
        """Add an event to memory"""
        event = event.copy()
        event.setdefault("timestamp", datetime.utcnow().isoformat())
        
        self._recent_events.append(event)
        self._pending_summarization.append(event)
        
        # Maintain sliding window
        if len(self._recent_events) > self.sliding_window_size:
            self._recent_events = self._recent_events[-self.sliding_window_size:]
        
        # Track relationships from messages
        if event.get("type") == "message":
            self._update_relationship_from_message(event)
        
        # Check if we should trigger summarization
        if len(self._pending_summarization) >= self.summarize_threshold:
            self._create_episodic_summary()
    
    def add_message(self, message: dict[str, Any]) -> None:
        """Add a message to memory"""
        self.add_event({
            "type": "message",
            "data": message,
        })
    
    def add_action(self, action: dict[str, Any]) -> None:
        """Add an action to memory"""
        self.add_event({
            "type": "action",
            "data": action,
        })
    
    def add_observation(self, observation: str, step_index: int) -> None:
        """Add an observation to memory"""
        self.add_event({
            "type": "observation",
            "content": observation,
            "step_index": step_index,
        })
    
    def set_arrival_context(
        self,
        location: str,
        from_location: str | None,
        reason: str,
        step_index: int,
    ) -> None:
        """Set context about how agent arrived at current location"""
        self._arrival_context = {
            "location": location,
            "from_location": from_location,
            "reason": reason,
            "step_index": step_index,
        }
    
    def get_arrival_context(self) -> dict[str, Any]:
        """Get context about how agent arrived at current location"""
        return self._arrival_context.copy()
    
    def _update_relationship_from_message(self, event: dict[str, Any]) -> None:
        """Update relationship memory from a message event"""
        data = event.get("data", {})
        from_agent = data.get("from_agent")
        from_name = data.get("from_agent_name", from_agent)
        step_index = data.get("step_index", 0)
        location = data.get("location")
        
        if not from_agent or from_agent == self.agent_id:
            return
        
        if from_agent not in self._relationships:
            self._relationships[from_agent] = RelationshipMemory(
                agent_id=from_agent,
                agent_name=from_name,
                first_met_step=step_index,
                first_met_location=location,
            )
        
        rel = self._relationships[from_agent]
        rel.interaction_count += 1
        rel.last_interaction_step = step_index
    
    def get_relationship(self, agent_id: str) -> RelationshipMemory | None:
        """Get relationship memory for a specific agent"""
        return self._relationships.get(agent_id)
    
    def update_relationship(
        self,
        agent_id: str,
        trust_delta: int = 0,
        sentiment: str | None = None,
        note: str | None = None,
    ) -> None:
        """Update relationship with another agent"""
        if agent_id not in self._relationships:
            return
        
        rel = self._relationships[agent_id]
        
        if trust_delta:
            rel.trust_level = max(1, min(10, rel.trust_level + trust_delta))
        
        if sentiment:
            rel.sentiment = sentiment
        
        if note:
            rel.notes.append(note)
            # Keep only recent notes
            if len(rel.notes) > 10:
                rel.notes = rel.notes[-10:]
    
    def _create_episodic_summary(self) -> None:
        """Create an episodic memory summary from pending events"""
        if not self._pending_summarization:
            return
        
        # Extract key information for summary
        messages = [e for e in self._pending_summarization if e.get("type") == "message"]
        actions = [e for e in self._pending_summarization if e.get("type") == "action"]
        
        if not messages and not actions:
            self._pending_summarization.clear()
            return
        
        # Determine step range
        steps = []
        for e in self._pending_summarization:
            if "step_index" in e:
                steps.append(e["step_index"])
            elif "data" in e and "step_index" in e["data"]:
                steps.append(e["data"]["step_index"])
        
        step_range = (min(steps) if steps else 0, max(steps) if steps else 0)
        
        # Collect participants
        participants = set()
        for msg in messages:
            data = msg.get("data", {})
            if data.get("from_agent"):
                participants.add(data.get("from_agent_name", data.get("from_agent")))
        
        # Collect locations
        locations = set()
        for e in self._pending_summarization:
            loc = e.get("location") or e.get("data", {}).get("location")
            if loc:
                locations.add(loc)
        
        # Generate summary (simplified - could be LLM-generated)
        summary_parts = []
        if messages:
            summary_parts.append(f"Had {len(messages)} exchanges")
            if participants:
                summary_parts.append(f"with {', '.join(list(participants)[:3])}")
        if actions:
            action_types = [a.get("data", {}).get("action_type", "action") for a in actions]
            summary_parts.append(f"Took actions: {', '.join(set(action_types))}")
        
        summary = " ".join(summary_parts) if summary_parts else "Minor activity"
        
        # Extract key facts from messages
        key_facts = []
        for msg in messages[-5:]:  # Last 5 messages
            content = msg.get("data", {}).get("content", "")
            if len(content) > 100:
                content = content[:100] + "..."
            if content:
                sender = msg.get("data", {}).get("from_agent_name", "Someone")
                key_facts.append(f"{sender}: \"{content}\"")
        
        # Create episodic memory
        self._episodic_counter += 1
        episodic = EpisodicMemory(
            id=f"ep_{self.agent_id}_{self._episodic_counter}",
            summary=summary,
            participants=list(participants),
            location=list(locations)[0] if locations else None,
            step_range=step_range,
            emotional_impact="neutral",  # Could be analyzed
            importance=min(10, len(messages) + len(actions)),
            key_facts=key_facts,
        )
        
        self._episodic_memories.append(episodic)
        
        # Keep only most important episodic memories
        if len(self._episodic_memories) > 20:
            # Sort by importance and keep top 20
            self._episodic_memories.sort(key=lambda x: x.importance, reverse=True)
            self._episodic_memories = self._episodic_memories[:20]
        
        self._pending_summarization.clear()
    
    def get_recent_events(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get recent events from sliding window"""
        if limit:
            return self._recent_events[-limit:]
        return self._recent_events.copy()
    
    def get_recent_messages(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent messages"""
        messages = [
            e["data"] for e in self._recent_events
            if e.get("type") == "message" and "data" in e
        ]
        return messages[-limit:]
    
    def get_episodic_memories(self, limit: int | None = None) -> list[EpisodicMemory]:
        """Get episodic memories, most recent first"""
        memories = sorted(
            self._episodic_memories,
            key=lambda x: x.step_range[1],
            reverse=True,
        )
        if limit:
            return memories[:limit]
        return memories
    
    def get_all_relationships(self) -> dict[str, RelationshipMemory]:
        """Get all relationship memories"""
        return self._relationships.copy()
    
    def get_conversation_context(self, max_recent: int = 10, max_episodic: int = 3) -> str:
        """Build a context string for conversation including memory"""
        context_parts = []
        
        # Arrival context
        if self._arrival_context:
            context_parts.append(
                f"I arrived at {self._arrival_context.get('location', 'this location')} "
                f"from {self._arrival_context.get('from_location', 'elsewhere')} "
                f"because: {self._arrival_context.get('reason', 'I needed to be here')}."
            )
        
        # Key episodic memories
        episodic = self.get_episodic_memories(max_episodic)
        if episodic:
            context_parts.append("\nKey memories from earlier:")
            for mem in episodic:
                context_parts.append(f"- {mem.summary}")
                if mem.key_facts:
                    context_parts.append(f"  Key fact: {mem.key_facts[0]}")
        
        # Relationship context
        relationships = self.get_all_relationships()
        if relationships:
            context_parts.append("\nPeople I've interacted with:")
            for rel in list(relationships.values())[:5]:
                trust_desc = "trusted" if rel.trust_level >= 7 else "known" if rel.trust_level >= 4 else "uncertain about"
                context_parts.append(
                    f"- {rel.agent_name}: {trust_desc} "
                    f"({rel.interaction_count} interactions, {rel.sentiment} feeling)"
                )
        
        return "\n".join(context_parts)
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize memory to dictionary for persistence"""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "recent_events": self._recent_events,
            "episodic_memories": [m.to_dict() for m in self._episodic_memories],
            "relationships": {k: v.to_dict() for k, v in self._relationships.items()},
            "arrival_context": self._arrival_context,
            "episodic_counter": self._episodic_counter,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentMemory":
        """Restore memory from dictionary"""
        memory = cls(
            agent_id=data["agent_id"],
            agent_name=data["agent_name"],
        )
        memory._recent_events = data.get("recent_events", [])
        memory._episodic_memories = [
            EpisodicMemory.from_dict(m) for m in data.get("episodic_memories", [])
        ]
        memory._relationships = {
            k: RelationshipMemory.from_dict(v)
            for k, v in data.get("relationships", {}).items()
        }
        memory._arrival_context = data.get("arrival_context", {})
        memory._episodic_counter = data.get("episodic_counter", 0)
        return memory
    
    def clear(self) -> None:
        """Clear all memory"""
        self._recent_events.clear()
        self._episodic_memories.clear()
        self._relationships.clear()
        self._pending_summarization.clear()
        self._arrival_context.clear()


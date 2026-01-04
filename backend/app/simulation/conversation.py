"""Conversation state management for multi-agent dialogues"""
import uuid
from enum import Enum
from datetime import datetime
from typing import Any, Callable
from collections import defaultdict


class ConversationState(str, Enum):
    """State of a conversation"""
    ACTIVE = "active"       # Conversation is ongoing, agents taking turns
    WAITING = "waiting"     # Waiting for next speaker to respond
    PAUSED = "paused"       # Conversation paused (e.g., movement happening)
    ENDED = "ended"         # Conversation has concluded


class ConversationType(str, Enum):
    """Type of conversation"""
    LOCATION = "location"   # Auto-joined by agents at same location
    EXPLICIT = "explicit"   # Explicitly started between specific agents
    BROADCAST = "broadcast" # One-to-many announcement


class Conversation:
    """
    Represents an active conversation between agents.
    Manages turn-taking, participant tracking, and conversation state.
    """
    
    def __init__(
        self,
        conversation_id: str | None = None,
        location: str | None = None,
        conversation_type: ConversationType = ConversationType.LOCATION,
        initiator_id: str | None = None,
    ):
        self.id = conversation_id or str(uuid.uuid4())
        self.location = location
        self.conversation_type = conversation_type
        self.initiator_id = initiator_id
        
        self.state = ConversationState.ACTIVE
        self.participants: set[str] = set()
        self.message_history: list[dict[str, Any]] = []
        
        # Turn management
        self._turn_order: list[str] = []
        self._current_turn_index: int = 0
        self._consecutive_passes: int = 0  # Track how many agents passed in a row
        self._max_consecutive_passes: int = 2  # End after this many passes
        
        # Timing
        self.started_at: datetime = datetime.utcnow()
        self.last_activity: datetime = datetime.utcnow()
        self.ended_at: datetime | None = None
        
        # Settings
        self.max_turns_per_step: int = 20  # Safety limit
        self._turns_this_step: int = 0
    
    def add_participant(self, agent_id: str) -> bool:
        """Add an agent to the conversation"""
        if agent_id not in self.participants:
            self.participants.add(agent_id)
            self._update_turn_order()
            return True
        return False
    
    def remove_participant(self, agent_id: str) -> bool:
        """Remove an agent from the conversation"""
        if agent_id in self.participants:
            self.participants.discard(agent_id)
            self._update_turn_order()
            
            # End conversation if too few participants
            if len(self.participants) < 2:
                self.end()
            return True
        return False
    
    def _update_turn_order(self) -> None:
        """Update the turn order based on current participants"""
        # Maintain existing order for current participants, append new ones
        current_participants = list(self.participants)
        new_order = [p for p in self._turn_order if p in current_participants]
        for p in current_participants:
            if p not in new_order:
                new_order.append(p)
        self._turn_order = new_order
        
        # Adjust current turn index if needed
        if self._current_turn_index >= len(self._turn_order):
            self._current_turn_index = 0
    
    def get_next_speaker(self) -> str | None:
        """Get the next agent who should speak"""
        if not self._turn_order or self.state != ConversationState.ACTIVE:
            return None
        
        if self._current_turn_index >= len(self._turn_order):
            self._current_turn_index = 0
        
        return self._turn_order[self._current_turn_index]
    
    def advance_turn(self, spoke: bool = True) -> None:
        """Advance to the next speaker"""
        if spoke:
            self._consecutive_passes = 0
        else:
            self._consecutive_passes += 1
        
        self._current_turn_index = (self._current_turn_index + 1) % max(len(self._turn_order), 1)
        self._turns_this_step += 1
        self.last_activity = datetime.utcnow()
    
    def add_message(self, message: dict[str, Any]) -> None:
        """Add a message to the conversation history"""
        self.message_history.append(message)
        self.last_activity = datetime.utcnow()
        self._consecutive_passes = 0  # Reset passes when someone speaks
    
    def should_continue(self) -> bool:
        """Determine if the conversation should continue"""
        if self.state != ConversationState.ACTIVE:
            return False
        
        # Not enough participants
        if len(self.participants) < 2:
            return False
        
        # Too many consecutive passes (everyone is done talking)
        if self._consecutive_passes >= min(len(self.participants), self._max_consecutive_passes):
            return False
        
        # Safety limit on turns per step
        if self._turns_this_step >= self.max_turns_per_step:
            return False
        
        return True
    
    def reset_step_counters(self) -> None:
        """Reset per-step counters (call at start of each simulation step)"""
        self._turns_this_step = 0
        self._consecutive_passes = 0
    
    def end(self) -> None:
        """End the conversation"""
        self.state = ConversationState.ENDED
        self.ended_at = datetime.utcnow()
    
    def pause(self) -> None:
        """Pause the conversation"""
        self.state = ConversationState.PAUSED
    
    def resume(self) -> None:
        """Resume a paused conversation"""
        if self.state == ConversationState.PAUSED:
            self.state = ConversationState.ACTIVE
    
    def get_context_for_agent(self, agent_id: str, max_messages: int = 20) -> list[dict[str, Any]]:
        """Get conversation context for a specific agent"""
        return self.message_history[-max_messages:]
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize conversation to dictionary"""
        return {
            "id": self.id,
            "location": self.location,
            "conversation_type": self.conversation_type.value,
            "state": self.state.value,
            "participants": list(self.participants),
            "message_count": len(self.message_history),
            "started_at": self.started_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


class ConversationManager:
    """
    Manages all active conversations in a simulation.
    Handles conversation creation, agent joining/leaving, and turn coordination.
    """
    
    def __init__(self):
        # Active conversations by ID
        self._conversations: dict[str, Conversation] = {}
        
        # Location-based conversations: location -> conversation_id
        self._location_conversations: dict[str, str] = {}
        
        # Agent's current conversations: agent_id -> set of conversation_ids
        self._agent_conversations: dict[str, set[str]] = defaultdict(set)
        
        # Agent locations for auto-join: agent_id -> location
        self._agent_locations: dict[str, str] = {}
        
        # Callbacks for conversation events
        self._on_conversation_event: list[Callable[[str, dict[str, Any]], None]] = []
    
    def update_agent_location(self, agent_id: str, new_location: str) -> list[str]:
        """
        Update an agent's location and manage conversation membership.
        Returns list of conversation IDs the agent joined.
        """
        old_location = self._agent_locations.get(agent_id)
        self._agent_locations[agent_id] = new_location
        
        joined_conversations = []
        
        # Leave location-based conversations at old location
        if old_location and old_location != new_location:
            old_conv_id = self._location_conversations.get(old_location)
            if old_conv_id and old_conv_id in self._conversations:
                conv = self._conversations[old_conv_id]
                if conv.conversation_type == ConversationType.LOCATION:
                    self._leave_conversation(agent_id, old_conv_id)
        
        # Join or create location-based conversation at new location
        if new_location:
            conv_id = self._get_or_create_location_conversation(new_location)
            if self._join_conversation(agent_id, conv_id):
                joined_conversations.append(conv_id)
        
        return joined_conversations
    
    def _get_or_create_location_conversation(self, location: str) -> str:
        """Get or create a location-based conversation"""
        if location in self._location_conversations:
            conv_id = self._location_conversations[location]
            if conv_id in self._conversations:
                conv = self._conversations[conv_id]
                if conv.state == ConversationState.ACTIVE:
                    return conv_id
        
        # Create new location-based conversation
        conv = Conversation(
            location=location,
            conversation_type=ConversationType.LOCATION,
        )
        self._conversations[conv.id] = conv
        self._location_conversations[location] = conv.id
        
        self._notify_event("conversation_created", conv.to_dict())
        
        return conv.id
    
    def start_explicit_conversation(
        self,
        initiator_id: str,
        target_agent_ids: list[str],
        location: str | None = None,
    ) -> str:
        """Start an explicit conversation between specific agents"""
        conv = Conversation(
            location=location,
            conversation_type=ConversationType.EXPLICIT,
            initiator_id=initiator_id,
        )
        
        # Add all participants
        conv.add_participant(initiator_id)
        for agent_id in target_agent_ids:
            conv.add_participant(agent_id)
        
        self._conversations[conv.id] = conv
        
        # Track agent memberships
        for agent_id in conv.participants:
            self._agent_conversations[agent_id].add(conv.id)
        
        self._notify_event("conversation_created", conv.to_dict())
        
        return conv.id
    
    def _join_conversation(self, agent_id: str, conversation_id: str) -> bool:
        """Have an agent join a conversation"""
        if conversation_id not in self._conversations:
            return False
        
        conv = self._conversations[conversation_id]
        if conv.add_participant(agent_id):
            self._agent_conversations[agent_id].add(conversation_id)
            self._notify_event("agent_joined", {
                "conversation_id": conversation_id,
                "agent_id": agent_id,
            })
            return True
        return False
    
    def _leave_conversation(self, agent_id: str, conversation_id: str) -> bool:
        """Have an agent leave a conversation"""
        if conversation_id not in self._conversations:
            return False
        
        conv = self._conversations[conversation_id]
        if conv.remove_participant(agent_id):
            self._agent_conversations[agent_id].discard(conversation_id)
            self._notify_event("agent_left", {
                "conversation_id": conversation_id,
                "agent_id": agent_id,
            })
            return True
        return False
    
    def join_conversation(self, agent_id: str, conversation_id: str) -> bool:
        """Public method to join a conversation"""
        return self._join_conversation(agent_id, conversation_id)
    
    def leave_conversation(self, agent_id: str, conversation_id: str) -> bool:
        """Public method to leave a conversation"""
        return self._leave_conversation(agent_id, conversation_id)
    
    def get_agent_conversations(self, agent_id: str) -> list[Conversation]:
        """Get all active conversations an agent is part of"""
        conv_ids = self._agent_conversations.get(agent_id, set())
        return [
            self._conversations[cid]
            for cid in conv_ids
            if cid in self._conversations and self._conversations[cid].state == ConversationState.ACTIVE
        ]
    
    def get_conversation(self, conversation_id: str) -> Conversation | None:
        """Get a conversation by ID"""
        return self._conversations.get(conversation_id)
    
    def get_location_conversation(self, location: str) -> Conversation | None:
        """Get the conversation at a specific location"""
        conv_id = self._location_conversations.get(location)
        if conv_id and conv_id in self._conversations:
            return self._conversations[conv_id]
        return None
    
    def get_agents_at_location(self, location: str) -> set[str]:
        """Get all agents at a specific location"""
        return {
            agent_id
            for agent_id, loc in self._agent_locations.items()
            if loc == location
        }
    
    def add_message_to_conversation(
        self,
        conversation_id: str,
        message: dict[str, Any],
    ) -> bool:
        """Add a message to a conversation"""
        if conversation_id not in self._conversations:
            return False
        
        conv = self._conversations[conversation_id]
        conv.add_message(message)
        
        self._notify_event("message_added", {
            "conversation_id": conversation_id,
            "message": message,
        })
        
        return True
    
    def get_conversations_needing_turns(self) -> list[Conversation]:
        """Get all conversations that need turn processing"""
        return [
            conv for conv in self._conversations.values()
            if conv.state == ConversationState.ACTIVE and conv.should_continue()
        ]
    
    def reset_step_counters(self) -> None:
        """Reset per-step counters for all conversations"""
        for conv in self._conversations.values():
            if conv.state == ConversationState.ACTIVE:
                conv.reset_step_counters()
    
    def cleanup_ended_conversations(self) -> list[str]:
        """Remove ended conversations and return their IDs"""
        ended_ids = [
            cid for cid, conv in self._conversations.items()
            if conv.state == ConversationState.ENDED
        ]
        
        for cid in ended_ids:
            conv = self._conversations.pop(cid, None)
            if conv:
                # Clean up location mapping
                if conv.location and self._location_conversations.get(conv.location) == cid:
                    del self._location_conversations[conv.location]
                
                # Clean up agent memberships
                for agent_id in conv.participants:
                    self._agent_conversations[agent_id].discard(cid)
        
        return ended_ids
    
    def end_conversation(self, conversation_id: str) -> bool:
        """End a specific conversation"""
        if conversation_id not in self._conversations:
            return False
        
        conv = self._conversations[conversation_id]
        conv.end()
        
        self._notify_event("conversation_ended", conv.to_dict())
        
        return True
    
    def on_event(self, callback: Callable[[str, dict[str, Any]], None]) -> None:
        """Register a callback for conversation events"""
        self._on_conversation_event.append(callback)
    
    def _notify_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Notify all registered callbacks of an event"""
        for callback in self._on_conversation_event:
            try:
                callback(event_type, data)
            except Exception:
                pass
    
    def clear(self) -> None:
        """Clear all conversations"""
        self._conversations.clear()
        self._location_conversations.clear()
        self._agent_conversations.clear()
        self._agent_locations.clear()
    
    def get_all_active_conversations(self) -> list[Conversation]:
        """Get all active conversations"""
        return [
            conv for conv in self._conversations.values()
            if conv.state == ConversationState.ACTIVE
        ]
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize manager state to dictionary"""
        return {
            "conversations": {
                cid: conv.to_dict()
                for cid, conv in self._conversations.items()
            },
            "agent_locations": dict(self._agent_locations),
            "location_conversations": dict(self._location_conversations),
        }


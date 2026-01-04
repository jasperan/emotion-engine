"""Message bus for agent-to-agent communication"""
from typing import Any, Callable
from datetime import datetime
from collections import defaultdict


class MessageBus:
    """
    In-memory message bus for routing messages between agents.
    Supports direct, room, and broadcast message types.
    """
    
    def __init__(self):
        # Message queues per agent
        self._agent_queues: dict[str, list[dict[str, Any]]] = defaultdict(list)
        
        # Room subscriptions: room_name -> set of agent_ids
        self._room_subscriptions: dict[str, set[str]] = defaultdict(set)
        
        # All agents for broadcast
        self._all_agents: set[str] = set()
        
        # Message history for persistence
        self._message_history: list[dict[str, Any]] = []
        
        # Event callbacks
        self._on_message_callbacks: list[Callable[[dict[str, Any]], None]] = []
    
    def register_agent(self, agent_id: str) -> None:
        """Register an agent with the message bus"""
        self._all_agents.add(agent_id)
        self._agent_queues[agent_id] = []
    
    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent from the message bus"""
        self._all_agents.discard(agent_id)
        self._agent_queues.pop(agent_id, None)
        # Remove from all rooms
        for room in self._room_subscriptions.values():
            room.discard(agent_id)
    
    def join_room(self, agent_id: str, room_name: str) -> None:
        """Subscribe an agent to a room"""
        self._room_subscriptions[room_name].add(agent_id)
    
    def leave_room(self, agent_id: str, room_name: str) -> None:
        """Unsubscribe an agent from a room"""
        self._room_subscriptions[room_name].discard(agent_id)
    
    def send_direct(
        self,
        from_agent_id: str,
        to_agent_id: str,
        content: str,
        step_index: int,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a direct message to a specific agent"""
        message = {
            "id": f"msg_{len(self._message_history)}",
            "from_agent": from_agent_id,
            "to_target": to_agent_id,
            "message_type": "direct",
            "content": content,
            "step_index": step_index,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if to_agent_id in self._agent_queues:
            self._agent_queues[to_agent_id].append(message)
        
        self._message_history.append(message)
        self._notify_callbacks(message)
        
        return message
    
    def send_to_room(
        self,
        from_agent_id: str,
        room_name: str,
        content: str,
        step_index: int,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a message to all agents in a room"""
        message = {
            "id": f"msg_{len(self._message_history)}",
            "from_agent": from_agent_id,
            "to_target": room_name,
            "message_type": "room",
            "content": content,
            "step_index": step_index,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Deliver to all room members except sender
        for agent_id in self._room_subscriptions.get(room_name, set()):
            if agent_id != from_agent_id:
                self._agent_queues[agent_id].append(message)
        
        self._message_history.append(message)
        self._notify_callbacks(message)
        
        return message
    
    def broadcast(
        self,
        from_agent_id: str | None,
        content: str,
        step_index: int,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Broadcast a message to all agents"""
        message = {
            "id": f"msg_{len(self._message_history)}",
            "from_agent": from_agent_id,
            "to_target": "broadcast",
            "message_type": "broadcast",
            "content": content,
            "step_index": step_index,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Deliver to all agents except sender
        for agent_id in self._all_agents:
            if agent_id != from_agent_id:
                self._agent_queues[agent_id].append(message)
        
        self._message_history.append(message)
        self._notify_callbacks(message)
        
        return message
    
    def system_message(
        self,
        content: str,
        step_index: int,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a system message to all agents"""
        return self.broadcast(None, content, step_index, metadata)
    
    def get_messages(self, agent_id: str, clear: bool = True) -> list[dict[str, Any]]:
        """Get pending messages for an agent"""
        messages = self._agent_queues.get(agent_id, []).copy()
        if clear:
            self._agent_queues[agent_id] = []
        return messages
    
    def get_history(
        self,
        run_id: str | None = None,
        from_agent_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get message history with optional filters"""
        result = self._message_history
        
        if from_agent_id:
            result = [m for m in result if m.get("from_agent") == from_agent_id]
        
        if limit:
            result = result[-limit:]
        
        return result
    
    def clear(self) -> None:
        """Clear all messages and history"""
        self._agent_queues.clear()
        self._room_subscriptions.clear()
        self._all_agents.clear()
        self._message_history.clear()
    
    def on_message(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback for new messages"""
        self._on_message_callbacks.append(callback)
    
    def _notify_callbacks(self, message: dict[str, Any]) -> None:
        """Notify all registered callbacks of a new message"""
        for callback in self._on_message_callbacks:
            try:
                callback(message)
            except Exception:
                pass  # Don't let callback errors break message delivery


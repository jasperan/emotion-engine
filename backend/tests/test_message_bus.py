"""Tests for the message bus"""
import pytest
from app.simulation.message_bus import MessageBus


class TestMessageBus:
    """Test cases for MessageBus"""
    
    def test_register_agent(self):
        """Test agent registration"""
        bus = MessageBus()
        bus.register_agent("agent1")
        
        assert "agent1" in bus._all_agents
        assert "agent1" in bus._agent_queues
    
    def test_unregister_agent(self):
        """Test agent unregistration"""
        bus = MessageBus()
        bus.register_agent("agent1")
        bus.unregister_agent("agent1")
        
        assert "agent1" not in bus._all_agents
        assert "agent1" not in bus._agent_queues
    
    def test_send_direct_message(self):
        """Test sending direct messages"""
        bus = MessageBus()
        bus.register_agent("sender")
        bus.register_agent("receiver")
        
        msg = bus.send_direct("sender", "receiver", "Hello!", step_index=1)
        
        assert msg["from_agent"] == "sender"
        assert msg["to_target"] == "receiver"
        assert msg["content"] == "Hello!"
        assert msg["message_type"] == "direct"
        
        # Receiver should have the message
        messages = bus.get_messages("receiver")
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello!"
        
        # Queue should be cleared after getting messages
        messages = bus.get_messages("receiver")
        assert len(messages) == 0
    
    def test_broadcast_message(self):
        """Test broadcasting messages"""
        bus = MessageBus()
        bus.register_agent("sender")
        bus.register_agent("receiver1")
        bus.register_agent("receiver2")
        
        bus.broadcast("sender", "Emergency!", step_index=1)
        
        # All receivers should get the message
        messages1 = bus.get_messages("receiver1")
        messages2 = bus.get_messages("receiver2")
        sender_messages = bus.get_messages("sender")
        
        assert len(messages1) == 1
        assert len(messages2) == 1
        assert len(sender_messages) == 0  # Sender doesn't receive own broadcast
    
    def test_room_message(self):
        """Test room-based messaging"""
        bus = MessageBus()
        bus.register_agent("agent1")
        bus.register_agent("agent2")
        bus.register_agent("agent3")
        
        bus.join_room("agent1", "shelter")
        bus.join_room("agent2", "shelter")
        # agent3 is not in the room
        
        bus.send_to_room("agent1", "shelter", "Anyone here?", step_index=1)
        
        # Only agent2 should receive (agent1 is sender, agent3 not in room)
        messages1 = bus.get_messages("agent1")
        messages2 = bus.get_messages("agent2")
        messages3 = bus.get_messages("agent3")
        
        assert len(messages1) == 0
        assert len(messages2) == 1
        assert len(messages3) == 0
    
    def test_message_history(self):
        """Test message history retrieval"""
        bus = MessageBus()
        bus.register_agent("agent1")
        bus.register_agent("agent2")
        
        bus.send_direct("agent1", "agent2", "Message 1", step_index=1)
        bus.send_direct("agent2", "agent1", "Message 2", step_index=2)
        bus.broadcast("agent1", "Message 3", step_index=3)
        
        history = bus.get_history()
        assert len(history) == 3
        
        # Filter by sender
        agent1_history = bus.get_history(from_agent_id="agent1")
        assert len(agent1_history) == 2
    
    def test_system_message(self):
        """Test system messages"""
        bus = MessageBus()
        bus.register_agent("agent1")
        
        msg = bus.system_message("System alert!", step_index=1)
        
        assert msg["from_agent"] is None
        assert msg["message_type"] == "broadcast"
        
        messages = bus.get_messages("agent1")
        assert len(messages) == 1
    
    def test_callback_on_message(self):
        """Test message callbacks"""
        bus = MessageBus()
        bus.register_agent("agent1")
        bus.register_agent("agent2")
        
        received_messages = []
        
        def callback(msg):
            received_messages.append(msg)
        
        bus.on_message(callback)
        bus.send_direct("agent1", "agent2", "Test", step_index=1)
        
        assert len(received_messages) == 1
        assert received_messages[0]["content"] == "Test"


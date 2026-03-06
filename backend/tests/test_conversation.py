"""Tests for the conversation management system"""
import pytest
from datetime import datetime

from app.simulation.conversation import (
    Conversation,
    ConversationManager,
    ConversationState,
    ConversationType,
)


class TestConversation:
    """Tests for the Conversation class"""
    
    def test_conversation_creation(self):
        """Test creating a new conversation"""
        conv = Conversation(
            location="shelter",
            conversation_type=ConversationType.LOCATION,
        )
        
        assert conv.id is not None
        assert conv.location == "shelter"
        assert conv.conversation_type == ConversationType.LOCATION
        assert conv.state == ConversationState.ACTIVE
        assert len(conv.participants) == 0
    
    def test_add_participant(self):
        """Test adding participants to a conversation"""
        conv = Conversation()
        
        assert conv.add_participant("agent1")
        assert conv.add_participant("agent2")
        assert not conv.add_participant("agent1")  # Already added
        
        assert len(conv.participants) == 2
        assert "agent1" in conv.participants
        assert "agent2" in conv.participants
    
    def test_remove_participant(self):
        """Test removing participants from a conversation"""
        conv = Conversation()
        conv.add_participant("agent1")
        conv.add_participant("agent2")
        conv.add_participant("agent3")
        
        assert conv.remove_participant("agent2")
        assert len(conv.participants) == 2
        assert "agent2" not in conv.participants
        
        # Removing last participant should end conversation
        conv.remove_participant("agent1")
        assert conv.state == ConversationState.ENDED
    
    def test_turn_order(self):
        """Test turn-taking logic"""
        conv = Conversation()
        conv.add_participant("agent1")
        conv.add_participant("agent2")
        conv.add_participant("agent3")
        
        # First speaker
        speaker = conv.get_next_speaker()
        assert speaker == "agent1"
        
        conv.advance_turn(spoke=True)
        assert conv.get_next_speaker() == "agent2"
        
        conv.advance_turn(spoke=True)
        assert conv.get_next_speaker() == "agent3"
        
        conv.advance_turn(spoke=True)
        assert conv.get_next_speaker() == "agent1"  # Cycles back
    
    def test_should_continue(self):
        """Test conversation continuation logic"""
        conv = Conversation()
        conv.add_participant("agent1")
        conv.add_participant("agent2")
        
        assert conv.should_continue()
        
        # Simulate everyone passing
        conv.advance_turn(spoke=False)
        conv.advance_turn(spoke=False)
        
        assert not conv.should_continue()
    
    def test_add_message(self):
        """Test adding messages to conversation history"""
        conv = Conversation()
        conv.add_message({"content": "Hello", "from_agent": "agent1"})
        conv.add_message({"content": "Hi there", "from_agent": "agent2"})
        
        assert len(conv.message_history) == 2
        assert conv.message_history[0]["content"] == "Hello"
    
    def test_conversation_end(self):
        """Test ending a conversation"""
        conv = Conversation()
        conv.end()
        
        assert conv.state == ConversationState.ENDED
        assert conv.ended_at is not None
        assert not conv.should_continue()


class TestConversationManager:
    """Tests for the ConversationManager class"""
    
    def test_manager_creation(self):
        """Test creating a conversation manager"""
        manager = ConversationManager()
        assert len(manager._conversations) == 0
    
    def test_update_agent_location(self):
        """Test updating agent locations (no auto-join)"""
        manager = ConversationManager()

        # First agent at shelter - no auto-join
        joined = manager.update_agent_location("agent1", "shelter")
        assert len(joined) == 0

        # Second agent at shelter - also no auto-join
        joined = manager.update_agent_location("agent2", "shelter")
        assert len(joined) == 0

        # Agents are tracked at location even without conversations
        agents = manager.get_agents_at_location("shelter")
        assert len(agents) == 2
    
    def test_agent_leaves_location_conv_on_move(self):
        """Test that agents leave location conversations when moving"""
        manager = ConversationManager()

        # Manually create a location conversation
        conv = manager.create_conversation(
            initiator_id="agent1",
            participant_ids={"agent1", "agent2"},
            location="shelter",
            topic="shelter talk",
        )
        # Also register their locations
        manager._agent_locations["agent1"] = "shelter"
        manager._agent_locations["agent2"] = "shelter"
        # Register as location conversation for leave-on-move to work
        manager._location_conversations["shelter"] = conv.id
        # Mark as LOCATION type so the leave-on-move logic triggers
        conv.conversation_type = ConversationType.LOCATION

        assert len(conv.participants) == 2

        # Agent1 moves to street
        manager.update_agent_location("agent1", "street")

        # Conversation ended since only 1 participant left
        assert "agent1" not in conv.participants
    
    def test_explicit_conversation(self):
        """Test starting an explicit conversation"""
        manager = ConversationManager()
        
        conv_id = manager.start_explicit_conversation(
            initiator_id="agent1",
            target_agent_ids=["agent2", "agent3"],
            location="shelter",
        )
        
        conv = manager.get_conversation(conv_id)
        assert conv is not None
        assert conv.conversation_type == ConversationType.EXPLICIT
        assert len(conv.participants) == 3
        assert "agent1" in conv.participants
    
    def test_get_agent_conversations(self):
        """Test getting all conversations for an agent"""
        manager = ConversationManager()

        # Create an explicit conversation
        manager.create_conversation(
            initiator_id="agent1",
            participant_ids={"agent1", "agent2"},
            location="shelter",
            topic="plan A",
        )

        # Also starts another explicit conversation
        manager.start_explicit_conversation(
            initiator_id="agent1",
            target_agent_ids=["agent3"],
        )

        convs = manager.get_agent_conversations("agent1")
        assert len(convs) == 2
    
    def test_add_message_to_conversation(self):
        """Test adding messages to a managed conversation"""
        manager = ConversationManager()

        conv = manager.create_conversation(
            initiator_id="agent1",
            participant_ids={"agent1", "agent2"},
            location="shelter",
            topic="chat",
        )

        result = manager.add_message_to_conversation(
            conv.id,
            {"content": "Hello everyone", "from_agent": "agent1"},
        )

        assert result
        assert len(conv.message_history) == 1
    
    def test_cleanup_ended_conversations(self):
        """Test cleanup of ended conversations"""
        manager = ConversationManager()

        conv = manager.create_conversation(
            initiator_id="agent1",
            participant_ids={"agent1", "agent2"},
            location="shelter",
            topic="chat",
        )
        conv.end()

        ended_ids = manager.cleanup_ended_conversations()
        assert conv.id in ended_ids
        assert conv.id not in manager._conversations
    
    def test_get_agents_at_location(self):
        """Test getting agents at a specific location"""
        manager = ConversationManager()
        
        manager.update_agent_location("agent1", "shelter")
        manager.update_agent_location("agent2", "shelter")
        manager.update_agent_location("agent3", "street")
        
        shelter_agents = manager.get_agents_at_location("shelter")
        assert len(shelter_agents) == 2
        assert "agent1" in shelter_agents
        assert "agent2" in shelter_agents
        assert "agent3" not in shelter_agents


class TestConversationTurnTaking:
    """Tests for natural conversation turn-taking"""
    
    def test_natural_conversation_flow(self):
        """Test that conversations flow naturally with turn-taking"""
        conv = Conversation(location="shelter")
        
        # Add 3 participants
        conv.add_participant("sarah")
        conv.add_participant("marcus")
        conv.add_participant("elena")
        
        # Simulate a natural conversation
        messages = [
            ("sarah", "We need to organize the supplies."),
            ("marcus", "I can help carry the heavy stuff."),
            ("elena", "Let me check if anyone needs medical attention."),
            ("sarah", "Good idea, Elena. Marcus, can you check the back room?"),
        ]
        
        for expected_speaker, content in messages:
            speaker = conv.get_next_speaker()
            assert speaker == expected_speaker
            
            conv.add_message({
                "content": content,
                "from_agent": speaker,
            })
            conv.advance_turn(spoke=True)
        
        assert len(conv.message_history) == 4
    
    def test_skip_silent_agents(self):
        """Test handling agents who choose not to speak"""
        conv = Conversation()
        
        conv.add_participant("agent1")
        conv.add_participant("agent2")
        conv.add_participant("agent3")
        
        # Agent1 speaks
        assert conv.get_next_speaker() == "agent1"
        conv.add_message({"content": "Hello", "from_agent": "agent1"})
        conv.advance_turn(spoke=True)
        
        # Agent2 stays silent
        assert conv.get_next_speaker() == "agent2"
        conv.advance_turn(spoke=False)
        
        # Agent3 speaks
        assert conv.get_next_speaker() == "agent3"
        conv.add_message({"content": "Hi agent1", "from_agent": "agent3"})
        conv.advance_turn(spoke=True)
        
        assert len(conv.message_history) == 2


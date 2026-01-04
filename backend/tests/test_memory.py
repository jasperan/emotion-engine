"""Tests for the agent memory system"""
import pytest
from datetime import datetime

from app.agents.memory import (
    AgentMemory,
    EpisodicMemory,
    RelationshipMemory,
)


class TestAgentMemory:
    """Tests for the AgentMemory class"""
    
    def test_memory_creation(self):
        """Test creating a new agent memory"""
        memory = AgentMemory(
            agent_id="agent1",
            agent_name="Dr. Sarah Chen",
        )
        
        assert memory.agent_id == "agent1"
        assert memory.agent_name == "Dr. Sarah Chen"
        assert len(memory.get_recent_events()) == 0
    
    def test_add_event(self):
        """Test adding events to memory"""
        memory = AgentMemory(agent_id="agent1", agent_name="Sarah")
        
        memory.add_event({
            "type": "observation",
            "content": "Water is rising",
            "step_index": 1,
        })
        
        events = memory.get_recent_events()
        assert len(events) == 1
        assert events[0]["content"] == "Water is rising"
    
    def test_add_message(self):
        """Test adding messages to memory"""
        memory = AgentMemory(agent_id="agent1", agent_name="Sarah")
        
        memory.add_message({
            "content": "Hello everyone",
            "from_agent": "agent2",
            "from_agent_name": "Marcus",
            "step_index": 1,
        })
        
        messages = memory.get_recent_messages()
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello everyone"
    
    def test_sliding_window(self):
        """Test that sliding window maintains limit"""
        memory = AgentMemory(
            agent_id="agent1",
            agent_name="Sarah",
            sliding_window_size=5,
        )
        
        for i in range(10):
            memory.add_event({
                "type": "observation",
                "content": f"Event {i}",
                "step_index": i,
            })
        
        events = memory.get_recent_events()
        assert len(events) == 5
        assert events[0]["content"] == "Event 5"  # Oldest kept
        assert events[-1]["content"] == "Event 9"  # Most recent
    
    def test_relationship_tracking(self):
        """Test that relationships are tracked from messages"""
        memory = AgentMemory(agent_id="agent1", agent_name="Sarah")
        
        memory.add_message({
            "content": "Hello Sarah",
            "from_agent": "agent2",
            "from_agent_name": "Marcus",
            "step_index": 1,
            "location": "shelter",
        })
        
        rel = memory.get_relationship("agent2")
        assert rel is not None
        assert rel.agent_name == "Marcus"
        assert rel.interaction_count == 1
        assert rel.first_met_step == 1
    
    def test_update_relationship(self):
        """Test updating relationship attributes"""
        memory = AgentMemory(agent_id="agent1", agent_name="Sarah")
        
        # Create relationship
        memory.add_message({
            "content": "Hi",
            "from_agent": "agent2",
            "from_agent_name": "Marcus",
            "step_index": 1,
        })
        
        # Update it
        memory.update_relationship(
            "agent2",
            trust_delta=2,
            sentiment="positive",
            note="Helped me carry supplies",
        )
        
        rel = memory.get_relationship("agent2")
        assert rel.trust_level == 7  # 5 + 2
        assert rel.sentiment == "positive"
        assert "Helped me carry supplies" in rel.notes
    
    def test_arrival_context(self):
        """Test setting and getting arrival context"""
        memory = AgentMemory(agent_id="agent1", agent_name="Sarah")
        
        memory.set_arrival_context(
            location="shelter",
            from_location="street",
            reason="Needed medical supplies",
            step_index=5,
        )
        
        context = memory.get_arrival_context()
        assert context["location"] == "shelter"
        assert context["from_location"] == "street"
        assert context["reason"] == "Needed medical supplies"
    
    def test_conversation_context(self):
        """Test building conversation context string"""
        memory = AgentMemory(agent_id="agent1", agent_name="Sarah")
        
        # Add arrival context
        memory.set_arrival_context(
            location="shelter",
            from_location="street",
            reason="Evacuating from flood",
            step_index=1,
        )
        
        # Add some interactions
        memory.add_message({
            "content": "Need help over here!",
            "from_agent": "agent2",
            "from_agent_name": "Marcus",
            "step_index": 2,
        })
        
        memory.update_relationship("agent2", trust_delta=1, sentiment="positive")
        
        context = memory.get_conversation_context()
        
        assert "shelter" in context
        assert "street" in context
        assert "Marcus" in context
    
    def test_serialization(self):
        """Test serializing and deserializing memory"""
        memory = AgentMemory(agent_id="agent1", agent_name="Sarah")
        
        memory.add_event({"type": "observation", "content": "Test", "step_index": 1})
        memory.add_message({
            "content": "Hello",
            "from_agent": "agent2",
            "from_agent_name": "Marcus",
            "step_index": 2,
        })
        
        # Serialize
        data = memory.to_dict()
        
        # Deserialize
        restored = AgentMemory.from_dict(data)
        
        assert restored.agent_id == "agent1"
        assert restored.agent_name == "Sarah"
        assert len(restored.get_recent_events()) == 2
        assert restored.get_relationship("agent2") is not None


class TestEpisodicMemory:
    """Tests for the EpisodicMemory dataclass"""
    
    def test_episodic_creation(self):
        """Test creating an episodic memory"""
        episodic = EpisodicMemory(
            id="ep_1",
            summary="Had a conversation about supplies",
            participants=["Sarah", "Marcus"],
            location="shelter",
            step_range=(1, 5),
            emotional_impact="positive",
            importance=7,
            key_facts=["Need more water", "Marcus will get supplies"],
        )
        
        assert episodic.id == "ep_1"
        assert len(episodic.participants) == 2
        assert episodic.step_range == (1, 5)
    
    def test_episodic_serialization(self):
        """Test serializing and deserializing episodic memory"""
        episodic = EpisodicMemory(
            id="ep_1",
            summary="Test summary",
            participants=["Sarah"],
            location="shelter",
            step_range=(1, 3),
            emotional_impact="neutral",
            importance=5,
            key_facts=["Fact 1"],
        )
        
        data = episodic.to_dict()
        restored = EpisodicMemory.from_dict(data)
        
        assert restored.id == "ep_1"
        assert restored.step_range == (1, 3)


class TestRelationshipMemory:
    """Tests for the RelationshipMemory dataclass"""
    
    def test_relationship_creation(self):
        """Test creating a relationship memory"""
        rel = RelationshipMemory(
            agent_id="agent2",
            agent_name="Marcus Thompson",
            first_met_step=1,
            first_met_location="shelter",
        )
        
        assert rel.agent_id == "agent2"
        assert rel.trust_level == 5  # Default
        assert rel.sentiment == "neutral"
    
    def test_relationship_serialization(self):
        """Test serializing and deserializing relationship memory"""
        rel = RelationshipMemory(
            agent_id="agent2",
            agent_name="Marcus",
            first_met_step=1,
            first_met_location="shelter",
            trust_level=7,
            sentiment="positive",
            notes=["Helped carry supplies"],
        )
        
        data = rel.to_dict()
        restored = RelationshipMemory.from_dict(data)
        
        assert restored.trust_level == 7
        assert len(restored.notes) == 1


class TestEpisodicSummarization:
    """Tests for automatic episodic summarization"""
    
    def test_auto_summarization(self):
        """Test that episodic memories are created automatically"""
        memory = AgentMemory(
            agent_id="agent1",
            agent_name="Sarah",
            summarize_threshold=5,  # Summarize after 5 events
        )
        
        # Add enough events to trigger summarization
        for i in range(7):
            memory.add_message({
                "content": f"Message {i}",
                "from_agent": "agent2",
                "from_agent_name": "Marcus",
                "step_index": i,
            })
        
        episodic = memory.get_episodic_memories()
        assert len(episodic) >= 1


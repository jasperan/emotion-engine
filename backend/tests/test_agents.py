"""Tests for agent classes"""
import pytest
from unittest.mock import patch, AsyncMock

from app.agents import HumanAgent, EnvironmentAgent, DesignerAgent
from app.schemas.persona import Persona
from app.llm.base import LLMResponse


class TestHumanAgent:
    """Test cases for HumanAgent"""
    
    def test_create_with_persona(self, sample_persona):
        """Test creating a human agent with a persona"""
        agent = HumanAgent(
            name="Test",
            persona=sample_persona,
        )
        
        assert agent.name == sample_persona.name
        assert agent.role == "human"
        assert agent.persona.age == 30
        assert agent.persona.occupation == "Tester"
    
    def test_create_default_persona(self):
        """Test creating a human agent with default persona"""
        agent = HumanAgent(name="Default Agent")
        
        assert agent.persona is not None
        assert agent.persona.name == "Default Agent"
    
    def test_dynamic_state_sync(self, sample_persona):
        """Test that dynamic state syncs with persona"""
        agent = HumanAgent(persona=sample_persona)
        
        assert agent.dynamic_state["health"] == sample_persona.health
        assert agent.dynamic_state["stress_level"] == sample_persona.stress_level
    
    def test_update_stress(self, sample_persona):
        """Test stress level updates"""
        agent = HumanAgent(persona=sample_persona)
        initial_stress = agent.dynamic_state["stress_level"]
        
        agent.update_stress(3)
        assert agent.dynamic_state["stress_level"] == initial_stress + 3
        
        # Test bounds
        agent.update_stress(100)
        assert agent.dynamic_state["stress_level"] == 10  # Max
        
        agent.update_stress(-100)
        assert agent.dynamic_state["stress_level"] == 1  # Min
    
    def test_update_health(self, sample_persona):
        """Test health updates"""
        agent = HumanAgent(persona=sample_persona)
        
        agent.update_health(-5)
        assert agent.dynamic_state["health"] == 5
        
        # Test bounds
        agent.update_health(-100)
        assert agent.dynamic_state["health"] == 0  # Min
        
        agent.update_health(100)
        assert agent.dynamic_state["health"] == 10  # Max
    
    def test_system_prompt_generation(self, sample_persona):
        """Test system prompt includes persona details"""
        agent = HumanAgent(persona=sample_persona)
        prompt = agent.get_system_prompt()
        
        assert sample_persona.name in prompt
        assert str(sample_persona.age) in prompt
        assert sample_persona.occupation in prompt
    
    def test_to_dict_includes_persona(self, sample_persona):
        """Test serialization includes persona"""
        agent = HumanAgent(persona=sample_persona)
        data = agent.to_dict()
        
        assert "persona" in data
        assert data["persona"]["name"] == sample_persona.name


class TestEnvironmentAgent:
    """Test cases for EnvironmentAgent"""
    
    def test_create_environment_agent(self):
        """Test creating an environment agent"""
        agent = EnvironmentAgent(
            name="Flood",
            environment_type="flood",
        )
        
        assert agent.role == "environment"
        assert agent.environment_type == "flood"
    
    def test_dynamics_config(self):
        """Test custom dynamics configuration"""
        config = {"intensity_growth": 0.2, "event_probability": 0.3}
        agent = EnvironmentAgent(dynamics_config=config)
        
        assert agent.dynamics_config["intensity_growth"] == 0.2
        assert agent.dynamics_config["event_probability"] == 0.3
    
    def test_system_prompt_includes_type(self):
        """Test system prompt includes environment type"""
        agent = EnvironmentAgent(environment_type="earthquake")
        prompt = agent.get_system_prompt()
        
        assert "earthquake" in prompt


class TestDesignerAgent:
    """Test cases for DesignerAgent"""
    
    def test_create_designer_agent(self):
        """Test creating a designer agent"""
        agent = DesignerAgent(
            name="Director",
            scenario_goals=["Test cooperation"],
        )
        
        assert agent.role == "designer"
        assert "Test cooperation" in agent.goals
    
    def test_record_observation(self):
        """Test recording observations"""
        agent = DesignerAgent()
        
        agent.record_observation("Agents cooperated well")
        agent.record_observation("Tension increased")
        
        assert len(agent.observations) == 2
        assert "Agents cooperated well" in agent.observations


@pytest.mark.asyncio
class TestAgentTick:
    """Test agent tick method with mocked LLM"""
    
    async def test_human_agent_tick(self, sample_persona, mock_llm_client):
        """Test human agent tick execution"""
        agent = HumanAgent(persona=sample_persona)
        agent._llm_client = mock_llm_client
        
        world_state = {
            "hazard_level": 5,
            "current_step": 1,
            "locations": {"test_location": {"description": "Test"}},
        }
        messages = [
            {"from_agent": "other", "content": "Help!", "message_type": "broadcast"}
        ]
        
        response = await agent.tick(world_state, messages)
        
        assert response is not None
        assert response.message is not None
        mock_llm_client.generate.assert_called_once()
    
    async def test_environment_agent_tick(self, mock_llm_client):
        """Test environment agent tick execution"""
        agent = EnvironmentAgent()
        agent._llm_client = mock_llm_client
        
        world_state = {
            "hazard_level": 3,
            "current_step": 5,
            "locations": {},
        }
        
        response = await agent.tick(world_state, [])
        
        assert response is not None
        mock_llm_client.generate.assert_called_once()


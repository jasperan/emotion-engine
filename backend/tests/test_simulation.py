"""Tests for simulation engine"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.simulation.engine import SimulationEngine, SimulationState
from app.simulation.message_bus import MessageBus
from app.models.run import Run, RunStatus
from app.models.scenario import Scenario


@pytest.mark.asyncio
class TestSimulationEngine:
    """Test cases for SimulationEngine"""
    
    async def test_engine_initialization(self, db_session):
        """Test engine initializes correctly"""
        engine = SimulationEngine(
            run_id="test-run-123",
            db_session=db_session,
        )
        
        assert engine.state == SimulationState.IDLE
        assert engine.current_step == 0
        assert engine.world_state is not None
    
    async def test_initialize_with_config(self, db_session):
        """Test initializing engine with scenario config"""
        engine = SimulationEngine(
            run_id="test-run-123",
            db_session=db_session,
        )
        
        config = {
            "config": {
                "max_steps": 25,
                "tick_delay": 0.1,
                "initial_state": {"hazard_level": 3},
            },
            "agent_templates": [
                {
                    "name": "Test Agent",
                    "role": "human",
                    "model_id": "test-model",
                    "provider": "ollama",
                    "persona": {
                        "name": "Test Agent",
                        "age": 30,
                        "sex": "non-binary",
                        "occupation": "Tester",
                    },
                }
            ],
        }
        
        with patch("app.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(config)
        
        assert engine.max_steps == 25
        assert engine.tick_delay == 0.1
        assert len(engine.agents) == 1
        assert engine.world_state.get("hazard_level") == 3
    
    async def test_create_human_agent(self, db_session):
        """Test creating a human agent from config"""
        engine = SimulationEngine(
            run_id="test-run-123",
            db_session=db_session,
        )
        
        config = {
            "name": "Dr. Test",
            "role": "human",
            "model_id": "gemma3:270m",
            "provider": "ollama",
            "persona": {
                "name": "Dr. Test",
                "age": 45,
                "sex": "female",
                "occupation": "Doctor",
            },
        }
        
        with patch("app.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            agent = engine._create_agent(config)
        
        assert agent.role == "human"
        assert agent.name == "Dr. Test"
        assert agent.persona.occupation == "Doctor"
    
    async def test_create_environment_agent(self, db_session):
        """Test creating an environment agent from config"""
        engine = SimulationEngine(
            run_id="test-run-123",
            db_session=db_session,
        )
        
        config = {
            "name": "Flood System",
            "role": "environment",
            "environment_type": "flood",
        }
        
        with patch("app.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            agent = engine._create_agent(config)
        
        assert agent.role == "environment"
        assert agent.environment_type == "flood"
    
    async def test_pause_sets_state(self, db_session):
        """Test pause sets the correct state"""
        engine = SimulationEngine(
            run_id="test-run-123",
            db_session=db_session,
        )
        engine.state = SimulationState.RUNNING
        
        await engine.pause()
        
        assert engine._pause_requested is True
    
    async def test_stop_sets_state(self, db_session):
        """Test stop sets the correct state"""
        # Create a mock run in the database
        run = Run(id="test-run-123", scenario_id="test-scenario", status=RunStatus.RUNNING)
        db_session.add(run)
        await db_session.commit()
        
        engine = SimulationEngine(
            run_id="test-run-123",
            db_session=db_session,
        )
        engine.state = SimulationState.RUNNING
        
        await engine.stop()
        
        assert engine.state == SimulationState.IDLE
        assert engine._stop_requested is True
    
    def test_compute_step_metrics(self, db_session):
        """Test metrics computation"""
        engine = SimulationEngine(
            run_id="test-run-123",
            db_session=db_session,
        )
        engine.world_state["hazard_level"] = 5
        
        # Add mock human agents
        mock_agent1 = MagicMock()
        mock_agent1.role = "human"
        mock_agent1.dynamic_state = {"health": 8, "stress_level": 4}
        
        mock_agent2 = MagicMock()
        mock_agent2.role = "human"
        mock_agent2.dynamic_state = {"health": 6, "stress_level": 6}
        
        engine.agents = {"agent1": mock_agent1, "agent2": mock_agent2}
        
        metrics = engine._compute_step_metrics()
        
        assert metrics["avg_health"] == 7.0  # (8 + 6) / 2
        assert metrics["avg_stress"] == 5.0  # (4 + 6) / 2
        assert metrics["hazard_level"] == 5
    
    def test_apply_environment_update(self, db_session):
        """Test applying environment updates to world state"""
        engine = SimulationEngine(
            run_id="test-run-123",
            db_session=db_session,
        )
        
        params = {
            "hazard_level": 7,
            "events": ["Water level rising"],
            "new_resources": ["lifeboat"],
            "affected_locations": ["street"],
        }
        
        engine._apply_environment_update(params)
        
        assert engine.world_state["hazard_level"] == 7
        assert "Water level rising" in engine.world_state["events"]
        assert "lifeboat" in engine.world_state["resources"]
        assert "street" in engine.world_state["locations"]


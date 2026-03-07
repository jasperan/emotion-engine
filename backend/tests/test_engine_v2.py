import pytest
from unittest.mock import AsyncMock, MagicMock
from app.simulation.engine_v2 import SimulationEngineV2
from app.simulation.heartbeat import HeartbeatScheduler, EventTrigger
from app.simulation.goal_tree import GoalTree, GoalLevel, GoalStatus
from app.simulation.governance import GovernanceGate, GovernanceConfig, GateStatus


def _make_human_agent(agent_id="a1", name="Alice", neuroticism=5,
                      conscientiousness=5, stress=50):
    agent = MagicMock()
    agent.id = agent_id
    agent.name = name
    agent.role = "human"
    agent.persona = MagicMock()
    agent.persona.neuroticism = neuroticism
    agent.persona.conscientiousness = conscientiousness
    agent.dynamic_state = {"stress_level": stress, "location": "shelter"}
    agent.goals = ["Survive"]
    agent.agent_memory = MagicMock()
    agent.agent_memory.intent = MagicMock()
    agent.agent_memory.intent.current_plan = None
    agent._action_feedback = []
    agent._pending_trust_changes = []
    return agent


def _make_env_agent(agent_id="env1"):
    agent = MagicMock()
    agent.id = agent_id
    agent.name = "Environment"
    agent.role = "environment"
    agent.dynamic_state = {}
    agent._action_feedback = []
    return agent


class TestEngineV2Initialization:
    def test_creates_heartbeat_scheduler(self):
        engine = SimulationEngineV2()
        assert isinstance(engine.heartbeat_scheduler, HeartbeatScheduler)

    def test_creates_goal_tree(self):
        engine = SimulationEngineV2()
        assert isinstance(engine.goal_tree, GoalTree)

    def test_creates_governance_gate(self):
        engine = SimulationEngineV2()
        assert isinstance(engine.governance_gate, GovernanceGate)


class TestHeartbeatIntegration:
    def test_register_agents(self):
        engine = SimulationEngineV2()
        agent = _make_human_agent()
        engine.register_agents_v2({"a1": agent})
        ready = engine.get_ready_agent_ids(1)
        assert "a1" in ready

    def test_high_neuroticism_beats_every_tick(self):
        engine = SimulationEngineV2()
        agent = _make_human_agent(neuroticism=9)
        engine.register_agents_v2({"a1": agent})
        engine.get_ready_agent_ids(1)
        ready = engine.get_ready_agent_ids(2)
        assert "a1" in ready

    def test_deliberate_agent_skips_ticks(self):
        engine = SimulationEngineV2()
        agent = _make_human_agent(neuroticism=2, conscientiousness=8)
        engine.register_agents_v2({"a1": agent})
        engine.get_ready_agent_ids(1)
        ready = engine.get_ready_agent_ids(2)
        assert "a1" not in ready


class TestGoalTreeIntegration:
    def test_mission_set(self):
        engine = SimulationEngineV2()
        engine.setup_mission("Ensure survival", step=0)
        assert engine.goal_tree.mission is not None

    def test_agent_goals_accessible(self):
        engine = SimulationEngineV2()
        engine.setup_mission("Survive", step=0)
        gid = engine.goal_tree.add_group_goal("Evacuate", ["a1"], step=1)
        engine.goal_tree.add_agent_goal("Find rope", "a1", gid, step=2)
        goals = engine.goal_tree.get_active_goals("a1")
        assert len(goals) == 1


class TestGovernanceIntegration:
    def test_freeze_on_governance_pause(self):
        engine = SimulationEngineV2()
        agent = _make_human_agent()
        engine.register_agents_v2({"a1": agent})
        engine.get_ready_agent_ids(1)
        engine.freeze_agent("a1")
        ready = engine.get_ready_agent_ids(2)
        assert "a1" not in ready

    def test_unfreeze_after_approval(self):
        engine = SimulationEngineV2()
        agent = _make_human_agent(neuroticism=9)  # base_interval=1, beats every tick
        engine.register_agents_v2({"a1": agent})
        engine.get_ready_agent_ids(1)
        engine.freeze_agent("a1")
        engine.unfreeze_agent("a1")
        ready = engine.get_ready_agent_ids(2)
        assert "a1" in ready

    def test_process_governance_resolutions(self):
        engine = SimulationEngineV2()
        agent = _make_human_agent()
        engine.register_agents_v2({"a1": agent})
        # Trigger a governance gate
        decision = engine.governance_gate.evaluate("a1", "Abandon child", "Fear", step=5)
        engine.freeze_agent("a1")
        # Resolve it
        engine.governance_gate.resolve(decision.id, approved=True, researcher_note="OK")
        results = engine.process_governance_resolutions()
        assert len(results) == 1
        assert results[0]["approved"] is True
        # Agent should be unfrozen
        ready = engine.get_ready_agent_ids(6)
        assert "a1" in ready


class TestV2State:
    def test_get_v2_state(self):
        engine = SimulationEngineV2()
        engine.setup_mission("Survive", step=0)
        state = engine.get_v2_state()
        assert "heartbeat" in state
        assert "goal_tree" in state
        assert "governance_audit" in state

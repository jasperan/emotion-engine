import pytest
from unittest.mock import MagicMock
from app.simulation.heartbeat import HeartbeatScheduler, EventTrigger


class TestHeartbeatScheduler:

    def _make_agent(self, agent_id="a1", role="human", neuroticism=5,
                    conscientiousness=5, stress_level=50):
        agent = MagicMock()
        agent.id = agent_id
        agent.role = role
        if role == "human":
            agent.persona = MagicMock()
            agent.persona.neuroticism = neuroticism
            agent.persona.conscientiousness = conscientiousness
            agent.dynamic_state = {"stress_level": stress_level}
        return agent

    def test_register_human_agent_default_interval(self):
        sched = HeartbeatScheduler()
        agent = self._make_agent(neuroticism=5, conscientiousness=5)
        sched.register(agent)
        assert sched._agents["a1"].base_interval == 2

    def test_register_high_neuroticism_interval_1(self):
        sched = HeartbeatScheduler()
        agent = self._make_agent(neuroticism=8)
        sched.register(agent)
        assert sched._agents["a1"].base_interval == 1

    def test_register_deliberate_agent_interval_3(self):
        sched = HeartbeatScheduler()
        agent = self._make_agent(neuroticism=2, conscientiousness=8)
        sched.register(agent)
        assert sched._agents["a1"].base_interval == 3

    def test_environment_agent_fixed_interval(self):
        sched = HeartbeatScheduler()
        agent = self._make_agent(agent_id="env1", role="environment")
        sched.register(agent)
        assert sched._agents["env1"].base_interval == 1

    def test_get_ready_agents_respects_interval(self):
        sched = HeartbeatScheduler()
        fast = self._make_agent("fast", neuroticism=8)
        slow = self._make_agent("slow", neuroticism=2, conscientiousness=8)
        sched.register(fast)
        sched.register(slow)
        ready = sched.get_ready_agents(1)
        assert "fast" in ready
        assert "slow" in ready
        ready = sched.get_ready_agents(2)
        assert "fast" in ready
        assert "slow" not in ready
        sched.get_ready_agents(3)
        ready = sched.get_ready_agents(4)
        assert "slow" in ready

    def test_stress_modifier_high_stress_doubles_speed(self):
        sched = HeartbeatScheduler()
        agent = self._make_agent(stress_level=90)
        sched.register(agent)
        effective = sched.get_effective_interval("a1")
        assert effective == 1

    def test_stress_modifier_low_stress_slows_down(self):
        sched = HeartbeatScheduler()
        agent = self._make_agent(stress_level=10)
        sched.register(agent)
        effective = sched.get_effective_interval("a1")
        assert effective == 3

    def test_event_trigger_bypasses_interval(self):
        sched = HeartbeatScheduler()
        agent = self._make_agent("slow", neuroticism=2, conscientiousness=8)
        sched.register(agent)
        sched.get_ready_agents(1)
        sched.add_event_trigger("slow", EventTrigger.DIRECT_MESSAGE)
        ready = sched.get_ready_agents(2)
        assert "slow" in ready

    def test_freeze_skips_agent(self):
        sched = HeartbeatScheduler()
        agent = self._make_agent(neuroticism=8)
        sched.register(agent)
        sched.get_ready_agents(1)
        sched.freeze("a1")
        ready = sched.get_ready_agents(2)
        assert "a1" not in ready

    def test_unfreeze_resumes_agent(self):
        sched = HeartbeatScheduler()
        agent = self._make_agent(neuroticism=8)
        sched.register(agent)
        sched.get_ready_agents(1)
        sched.freeze("a1")
        sched.get_ready_agents(2)
        sched.unfreeze("a1")
        ready = sched.get_ready_agents(3)
        assert "a1" in ready

    def test_update_stress_recalculates_interval(self):
        sched = HeartbeatScheduler()
        agent = self._make_agent(stress_level=50)
        sched.register(agent)
        assert sched.get_effective_interval("a1") == 2
        sched.update_stress("a1", 90)
        assert sched.get_effective_interval("a1") == 1

    def test_to_dict_and_from_dict_roundtrip(self):
        sched = HeartbeatScheduler()
        agent = self._make_agent(neuroticism=8)
        sched.register(agent)
        sched.get_ready_agents(1)
        data = sched.to_dict()
        sched2 = HeartbeatScheduler.from_dict(data)
        assert sched2._agents["a1"].base_interval == 1
        assert sched2._agents["a1"].next_beat_at == sched._agents["a1"].next_beat_at

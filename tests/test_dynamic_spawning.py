"""Tests for dynamic agent spawning / departure (emotionsim/simulation/dynamic_spawner.py)."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from emotionsim.core.config import Settings
from emotionsim.simulation.dynamic_spawner import DynamicSpawner, SpawnConfig
from emotionsim.simulation.engine import SimulationEngine


class TestSpawnerRules:
    def test_interval_trigger(self):
        s = DynamicSpawner(SpawnConfig(interval_steps=3, max_extra_agents=5))
        assert s.should_spawn(3, hazard=2, spawned_count=0) is True
        assert s.should_spawn(1, hazard=2, spawned_count=0) is False

    def test_surge_trigger(self):
        s = DynamicSpawner(SpawnConfig(interval_steps=3, max_extra_agents=5))
        assert s.should_spawn(1, hazard=8, spawned_count=0) is True

    def test_cap_respected(self):
        s = DynamicSpawner(SpawnConfig(interval_steps=1, max_extra_agents=2))
        assert s.should_spawn(1, hazard=2, spawned_count=2) is False

    def test_persona_is_complete(self):
        s = DynamicSpawner(SpawnConfig(seed=7))
        p = s.build_persona()
        for key in ("name", "occupation", "location", "extraversion", "agreeableness",
                    "conscientiousness", "neuroticism", "openness", "leadership",
                    "stress_level", "health", "sex", "age", "goals"):
            assert key in p, key
        assert 1 <= p["extraversion"] <= 10

    def test_deterministic_spawns(self):
        a = DynamicSpawner(SpawnConfig(seed=42))
        b = DynamicSpawner(SpawnConfig(seed=42))
        assert a.build_persona()["name"] == b.build_persona()["name"]
        assert a.build_persona()["occupation"] == b.build_persona()["occupation"]

    def test_unique_names(self):
        s = DynamicSpawner(SpawnConfig(seed=3))
        names = {s.build_persona()["name"] for _ in range(8)}
        assert len(names) == 8  # no duplicates within the pool

    def test_evict_rule(self):
        s = DynamicSpawner()

        class _A:
            class persona:
                health = 8
                stress_level = 5

            dynamic_state = {"health": 0, "stress_level": 5}

        assert s.should_evict(_A()) is True

        class _B:
            class persona:
                health = 8
                stress_level = 5

            dynamic_state = {"health": 8, "stress_level": 9}

        assert s.should_evict(_B()) is True

        class _C:
            class persona:
                health = 8
                stress_level = 5

            dynamic_state = {"health": 7, "stress_level": 4}

        assert s.should_evict(_C()) is False


@patch("emotionsim.simulation.engine.get_settings")
def test_engine_spawns_and_evicts(mock_settings, db_session, sample_persona):
    """End-to-end: arrivals join, exhausted agents leave, events fire."""
    mock_settings.return_value = Settings(
        dynamic_spawning_enabled=True,
        spawn_interval_steps=1,   # spawn every step
        spawn_max_extra_agents=2,
        spawn_location="test_location",
        spawn_evict_health_threshold=1,
        spawn_evict_stress_threshold=9,
    )
    engine = SimulationEngine(run_id="dyn-run-1", db_session=db_session)
    engine.current_step = 1  # step 1: interval-1 trigger fires
    engine.world_state = {
        "hazard_level": 3,
        "locations": {"test_location": {"nearby": []}},
        "agents": {},
    }
    events = []

    def _on_evt(event, data):
        events.append((event, data))

    engine.on_event = _on_evt

    # One existing, nearly-dead human agent who should leave.
    from emotionsim.agents.human import HumanAgent

    dying = HumanAgent(persona=sample_persona)
    dying.dynamic_state["health"] = 0
    dying.dynamic_state["location"] = "test_location"
    engine._register_agent(dying)
    engine.message_bus.register_agent(dying.id, dying.name)
    engine.supervisor.register_agent(dying.id, dying.name)
    engine._agent_locations[dying.id] = "test_location"

    async def _run():
        await engine._maybe_dynamic_population([], [])
        await engine._maybe_dynamic_population([], [])

    asyncio.run(_run())

    # Evacuees spawned (interval-1: one per call) and the dying agent left.
    spawned = [e for e, _ in events if e == "agent_spawned"]
    left = [e for e, _ in events if e == "agent_left"]
    assert len(spawned) == 2
    assert len(left) == 1
    # Spawned agents are registered in the live population (cap is 2).
    assert engine._spawned_count == 2
    assert len(engine.agents) == 2
    # Dying agent removed from live agents.
    assert dying.id not in engine.agents


@patch("emotionsim.simulation.engine.get_settings")
def test_engine_disabled_no_spawns(mock_settings, db_session):
    mock_settings.return_value = Settings(dynamic_spawning_enabled=False)
    engine = SimulationEngine(run_id="dyn-run-2", db_session=db_session)
    assert engine._dynamic_spawner is None
    engine.world_state = {"hazard_level": 9, "locations": {"shelter": {}}, "agents": {}}
    events = []

    def _on_evt(event, data):
        events.append((event, data))

    engine.on_event = _on_evt

    async def _run():
        await engine._maybe_dynamic_population([], [])

    asyncio.run(_run())
    assert not [e for e, _ in events if e == "agent_spawned"]


@patch("emotionsim.simulation.engine.get_settings")
def test_full_run_completes_with_spawning(mock_settings, db_session):
    """A stub-LLM run with spawning enabled completes end-to-end."""
    mock_settings.return_value = Settings(
        dynamic_spawning_enabled=True,
        spawn_interval_steps=2,
        spawn_max_extra_agents=2,
        spawn_location="shelter",
        agent_tick_timeout=30,
        llm_backend="stub",
    )
    engine = SimulationEngine(run_id="dyn-run-3", db_session=db_session)

    async def _setup():
        # minimal scenario: 1 human + world
        await engine.initialize({
            "config": {
                "max_steps": 4,
                "initial_state": {
                    "hazard_level": 2,
                    "locations": {"shelter": {"nearby": []}, "street": {"nearby": ["shelter"]}},
                },
            },
            "agent_templates": [
                {
                    "name": "Static Resident",
                    "role": "human",
                    "persona": {
                        "name": "Static Resident",
                        "age": 30,
                        "occupation": "tester",
                        "sex": "non-binary",
                        "location": "shelter",
                        "extraversion": 5,
                        "agreeableness": 5,
                        "conscientiousness": 5,
                        "neuroticism": 5,
                        "openness": 5,
                        "leadership": 5,
                        "stress_level": 5,
                        "health": 8,
                    },
                }
            ],
            "seed": 42,
        })
        # Manually force spawn/evict ticks (loop is stubbed below).
        for step in (2, 3, 4):
            engine.current_step = step
            await engine._maybe_dynamic_population([], [])

    asyncio.run(_setup())
    assert engine._spawned_count >= 1
    assert len(engine.agents) >= 2  # original + evacuees
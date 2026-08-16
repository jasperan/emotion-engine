"""Step 2 (MiroFish): LightweightAgent hybrid populations for 100+ scaling.

Covers:
- background agents tick with zero LLM calls
- promotion/demotion round-trips (unit + engine level)
- per-step LLM-agent budget: with 100+ background agents + 1 foreground,
  only the foreground agent calls the LLM
- all background agents still produce actions/cinematic records
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from emotionsim.agents.human import HumanAgent
from emotionsim.core.config import Settings
from emotionsim.llm.base import LLMResponse
from emotionsim.models.run import Run, RunStatus
from emotionsim.models.step import Step
from emotionsim.schemas.agent import AgentResponse
from emotionsim.schemas.persona import Persona
from emotionsim.simulation.engine import SimulationEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_persona(**overrides) -> Persona:
    defaults = dict(
        name="Test Agent",
        age=30,
        sex="non-binary",
        occupation="Tester",
        openness=5,
        conscientiousness=5,
        extraversion=5,
        agreeableness=5,
        neuroticism=5,
        risk_tolerance=5,
        empathy_level=5,
        leadership=5,
        backstory="A test agent for unit testing",
        stress_level=3,
        health=10,
        location="Town Square",
    )
    defaults.update(overrides)
    return Persona(**defaults)


def _act_response_json() -> str:
    return json.dumps({
        "action": "She hurries toward the hill.",
        "speech": "We need high ground!",
        "thought": "The water is rising fast.",
        "emotion": "fear",
        "move_to": "Hill",
        "stress_level": 6,
    })


def _think_response_json() -> str:
    return json.dumps({
        "urgency": "medium",
        "assessment": "Water is rising",
        "top_need": "shelter",
    })


def _plan_response_json() -> str:
    return json.dumps({
        "goal": "Reach high ground",
        "steps": ["Move to Hill"],
        "success_criteria": "Safe",
        "fallback": None,
    })


def _mock_generate(**kwargs) -> LLMResponse:
    """Route mock LLM responses by system prompt (think / plan / act)."""
    system = kwargs.get("system") or ""
    if "analyzing a situation" in system:
        content = _think_response_json()
    elif "creating an action plan" in system:
        content = _plan_response_json()
    else:
        content = _act_response_json()
    return LLMResponse(content=content, raw_response={}, usage={})


def _locations() -> dict:
    return {
        "locations": {
            "Town Square": {"description": "A flooded square", "nearby": ["Hill"], "items": []},
            "Hill": {"description": "High ground", "nearby": ["Town Square"], "items": []},
            "School": {"description": "A shelter", "nearby": ["Town Square"], "items": []},
        }
    }


def _make_run(db_session, run_id: str) -> None:
    db_session.add(Run(id=run_id, scenario_id="scenario-hyb", status=RunStatus.PENDING))


# ---------------------------------------------------------------------------
# Unit: background behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_background_tick_makes_no_llm_calls():
    """A background agent's tick never calls the LLM and returns a response."""
    agent = HumanAgent(
        name="BG",
        persona=_make_persona(extraversion=8, leadership=3, location="Town Square"),
        background=True,
    )
    with patch(
        "emotionsim.agents.human.LLMRouter.generate_with_fallback",
        AsyncMock(side_effect=AssertionError("background agents must not call the LLM")),
    ), patch(
        "emotionsim.agents.base.LLMRouter.generate_with_fallback",
        AsyncMock(side_effect=AssertionError("background agents must not call the LLM")),
    ):
        resp = await agent.tick(
            {"current_step": 1, "agents": {}, "locations": {}},
            messages=[],
        )
    assert isinstance(resp, AgentResponse)
    assert resp.reasoning  # rule-based reasoning present


@pytest.mark.asyncio
async def test_foreground_tick_calls_llm():
    """A foreground agent still uses the full cognitive LLM path."""
    agent = HumanAgent(name="FG", persona=_make_persona(), background=False)
    mock_generate = AsyncMock(side_effect=lambda **kw: _mock_generate(**kw))
    with patch("emotionsim.agents.human.LLMRouter.generate_with_fallback", mock_generate), \
         patch("emotionsim.agents.base.LLMRouter.generate_with_fallback", mock_generate):
        resp = await agent.tick({"current_step": 1, "agents": {}, "locations": {}}, messages=[])
    assert mock_generate.await_count >= 1
    assert isinstance(resp, AgentResponse)


def test_promotion_demotion_round_trip_unit():
    """promote()/demote() flip the mode and should_promote() fires on triggers."""
    agent = HumanAgent(
        name="BG",
        persona=_make_persona(leadership=9, stress_level=2),
        background=True,
    )
    assert agent.background is True
    # Natural leader under low stress
    assert agent.should_promote(addressed_directly=False, in_active_scene=False) is True
    # Addressed directly (regardless of traits)
    assert agent.should_promote(addressed_directly=True, in_active_scene=False) is True

    agent.promote("addressed directly")
    assert agent.background is False
    assert agent.dynamic_state["_background"] is False

    agent.demote()
    assert agent.background is True
    assert agent.dynamic_state["_background"] is True
    assert agent._steps_since_promotion == 0


# ---------------------------------------------------------------------------
# Engine: 100+ hybrid population with budget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_100_agents_only_foreground_calls_llm(db_session):
    """100 background + 1 foreground agent, budget=1 → only Aria calls the LLM."""
    run_id = "run-hyb-100"
    db_session.add(Run(id=run_id, scenario_id="scenario-hyb", status=RunStatus.PENDING))
    await db_session.commit()

    templates = []
    # Foreground core cast member
    templates.append({
        "name": "Aria",
        "role": "human",
        "model_id": "test-model",
        "provider": "ollama",
        "persona": {
            "name": "Aria", "age": 30, "sex": "female", "occupation": "Nurse",
            "leadership": 5, "stress_level": 5, "extraversion": 5,
            "location": "Town Square",
        },
    })
    # 100 background agents (no promotion triggers)
    for i in range(100):
        templates.append({
            "name": f"Survivor {i:03d}",
            "role": "human",
            "model_id": "test-model",
            "provider": "ollama",
            "background": True,
            "persona": {
                "name": f"Survivor {i:03d}", "age": 20 + (i % 50), "sex": "non-binary",
                "occupation": "Civilian",
                "leadership": 3, "stress_level": 7, "extraversion": 3,
                "location": "Town Square" if i % 2 == 0 else "School",
            },
        })

    config = {
        "config": {"max_steps": 2, "tick_delay": 0.001, "seed": 42, "initial_state": {"hazard_level": 4, **_locations()}},
        "agent_templates": templates,
    }

    events: list[tuple[str, dict]] = []
    with patch(
        "emotionsim.simulation.engine.get_settings",
        return_value=Settings(
            max_llm_agents_per_step=1,
            background_demote_after_steps=1,
            scene_mode=False,
            max_concurrent_llm_calls=1,
            graph_memory_enabled=False,
        ),
    ):
        engine = SimulationEngine(
            run_id=run_id,
            db_session=db_session,
            on_event=lambda t, d: events.append((t, d)),
        )
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(config)

    assert len(engine.agents) == 101
    assert sum(1 for a in engine.agents.values() if a.background) == 100

    # Deterministic: every human responds when gated
    for agent in engine.agents.values():
        agent.should_respond = lambda *a, **k: True

    agent_names = [a.name for a in engine.agents.values()]
    llm_calls: list[tuple[int, str]] = []  # (step, agent_name)

    def _record_generate(**kwargs):
        system = kwargs.get("system") or ""
        who = next((n for n in agent_names if n in system), None)
        if who is not None:
            llm_calls.append((engine.current_step, who))
        return _mock_generate(**kwargs)

    with patch(
        "emotionsim.agents.human.LLMRouter.generate_with_fallback",
        AsyncMock(side_effect=_record_generate),
    ), patch(
        "emotionsim.agents.base.LLMRouter.generate_with_fallback",
        AsyncMock(side_effect=_record_generate),
    ):
        await engine.start()

    assert engine.current_step == 2

    # Per-step budget honored: at most 1 distinct agent calls the LLM per step
    per_step: dict[int, set[str]] = {}
    for step, name in llm_calls:
        per_step.setdefault(step, set()).add(name)
    assert per_step  # LLM calls happened
    assert all(len(names) <= 1 for names in per_step.values())

    # Only the core foreground agent or *promoted* background agents call the
    # LLM (no unpromoted background agent may ever call it)
    callers = {name for _, name in llm_calls}
    promoted = {d["agent_name"] for t, d in events if t == "agent_promoted"}
    assert callers <= {"Aria"} | promoted
    # Promotion/demotion round-trip itself is covered deterministically by
    # test_engine_promotion_demotion_round_trip.

    # All 100 background agents produced cinematic records (they acted)
    result = await db_session.execute(
        select(Step).where(Step.run_id == run_id).order_by(Step.step_index)
    )
    steps = result.scalars().all()
    assert len(steps) == 2
    for step in steps:
        cinematic = [a for a in step.actions if a.get("action_type") == "cinematic"]
        assert len(cinematic) >= 101  # Aria + 100 background agents
        bg_records = [a for a in cinematic if a["parameters"].get("background")]
        assert len(bg_records) >= 100


# ---------------------------------------------------------------------------
# Engine: promotion + demotion round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_promotion_demotion_round_trip(db_session):
    """A background leader is promoted on step 1 (LLM used), demoted on step 2."""
    run_id = "run-hyb-roundtrip"
    db_session.add(Run(id=run_id, scenario_id="scenario-hyb", status=RunStatus.PENDING))
    await db_session.commit()

    config = {
        "config": {"max_steps": 2, "tick_delay": 0.001, "seed": 7, "initial_state": {"hazard_level": 4, **_locations()}},
        "agent_templates": [
            {
                "name": "Lena",
                "role": "human",
                "model_id": "test-model",
                "provider": "ollama",
                "background": True,
                "persona": {
                    "name": "Lena", "age": 42, "sex": "female", "occupation": "Coordinator",
                    "leadership": 9, "stress_level": 2, "extraversion": 5,
                    "location": "Town Square",
                },
            }
        ],
    }

    events: list[tuple[str, dict]] = []
    with patch(
        "emotionsim.simulation.engine.get_settings",
        return_value=Settings(
            max_llm_agents_per_step=1,
            background_demote_after_steps=1,
            scene_mode=False,
            max_concurrent_llm_calls=1,
            graph_memory_enabled=False,
        ),
    ):
        engine = SimulationEngine(
            run_id=run_id,
            db_session=db_session,
            on_event=lambda t, d: events.append((t, d)),
        )
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(config)

    lena = next(a for a in engine.agents.values() if a.name == "Lena")
    assert lena.background is True

    for agent in engine.agents.values():
        agent.should_respond = lambda *a, **k: True

    agent_names = [a.name for a in engine.agents.values()]
    llm_calls: list[tuple[int, str]] = []

    def _record_generate(**kwargs):
        system = kwargs.get("system") or ""
        who = next((n for n in agent_names if n in system), None)
        if who is not None:
            llm_calls.append((engine.current_step, who))
        return _mock_generate(**kwargs)

    with patch(
        "emotionsim.agents.human.LLMRouter.generate_with_fallback",
        AsyncMock(side_effect=_record_generate),
    ), patch(
        "emotionsim.agents.base.LLMRouter.generate_with_fallback",
        AsyncMock(side_effect=_record_generate),
    ):
        await engine.start()

    # Step 1: promoted → LLM used. Step 2: demoted → no LLM.
    step_1_callers = {name for step, name in llm_calls if step == 1}
    assert "Lena" in step_1_callers
    assert all(step == 1 for step, _ in llm_calls)

    # Round-trip: background → foreground → background
    assert lena.background is True
    assert lena.started_background is True

    event_types = [t for t, _ in events]
    assert "agent_promoted" in event_types
    assert "agent_demoted" in event_types

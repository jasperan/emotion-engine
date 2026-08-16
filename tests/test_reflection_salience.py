"""Step 4: batched LLM reflection + memory salience (importance-weighted recall).

Covers:
- reflection fires every N steps and stores summary + lessons in episodic memory
- reflection does NOT fire on non-interval steps (no extra LLM calls)
- importance-weighted recall: high-importance old memory beats recent low-importance
- get_conversation_context uses salience when current_step is provided,
  recency otherwise (backward compatible)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from emotionsim.agents.human import HumanAgent
from emotionsim.agents.memory import AgentMemory
from emotionsim.core.config import Settings
from emotionsim.llm.base import LLMResponse
from emotionsim.schemas.persona import Persona


def _make_persona(**overrides) -> Persona:
    defaults = dict(
        name="Test Agent",
        age=30,
        sex="non-binary",
        occupation="Tester",
        openness=5, conscientiousness=5, extraversion=5, agreeableness=5,
        neuroticism=5, risk_tolerance=5, empathy_level=5, leadership=5,
        backstory="A test agent", stress_level=3, health=10,
        location="test_location",
    )
    defaults.update(overrides)
    return Persona(**defaults)


def _act_json() -> str:
    return json.dumps({
        "action": "She checks the water level.",
        "speech": "The water is rising.",
        "thought": "We must move soon.",
        "emotion": "focus",
        "move_to": None,
        "stress_level": 5,
    })


def _reflection_json() -> str:
    return json.dumps({
        "summary": "The water rises faster at night.",
        "lessons": ["Check the tide before crossing", "Stick with Maria"],
        "importance": 8,
    })


def _route_by_system(**kwargs) -> LLMResponse:
    system = kwargs.get("system") or ""
    if "reflecting on what just happened" in system:
        return LLMResponse(content=_reflection_json())
    return LLMResponse(content=_act_json())


def _set_plan(agent: HumanAgent) -> None:
    from emotionsim.agents.intent_memory import Plan
    agent.agent_memory.intent.set_plan(Plan(
        goal="Reach high ground",
        steps=["Move to Hill"],
        current_step=0,
        created_at_step=0,
        success_criteria="Safe",
        fallback=None,
        deadline_step=50,
        retry_count=0,
    ))


@pytest.mark.asyncio
async def test_reflection_fires_on_interval_and_stores_lessons():
    """At step 5 (interval), the agent reflects; lessons land in episodic memory."""
    agent = HumanAgent(name="Test Agent", persona=_make_persona())
    _set_plan(agent)

    calls = []

    def _route(**kwargs):
        calls.append(kwargs.get("system") or "")
        return _route_by_system(**kwargs)

    with patch("emotionsim.core.config.get_settings",
               return_value=Settings(reflection_interval_steps=5)), \
         patch("emotionsim.agents.human.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_route)), \
         patch("emotionsim.agents.base.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_route)):
        await agent.tick(
            {"current_step": 5, "hazard_level": 5,
             "locations": {"test_location": {"nearby": []}}, "agents": {}},
            messages=[],
        )

    # act + reflection = 2 LLM calls
    assert len(calls) == 2
    assert any("reflecting on what just happened" in c for c in calls)

    summaries = [m.summary for m in agent.agent_memory.get_episodic_memories()]
    assert "The water rises faster at night." in summaries
    assert any("Check the tide before crossing" in s for s in summaries)
    assert any("Stick with Maria" in s for s in summaries)
    # Lessons carry importance
    assert any(m.importance == 8 for m in agent.agent_memory.get_episodic_memories())


@pytest.mark.asyncio
async def test_reflection_does_not_fire_off_interval():
    """At step 4 (off interval), only the act phase runs — no reflection call."""
    agent = HumanAgent(name="Test Agent", persona=_make_persona())
    _set_plan(agent)

    calls = []

    def _route(**kwargs):
        calls.append(kwargs.get("system") or "")
        return _route_by_system(**kwargs)

    with patch("emotionsim.core.config.get_settings",
               return_value=Settings(reflection_interval_steps=5)), \
         patch("emotionsim.agents.human.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_route)), \
         patch("emotionsim.agents.base.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_route)):
        await agent.tick(
            {"current_step": 4, "hazard_level": 5,
             "locations": {"test_location": {"nearby": []}}, "agents": {}},
            messages=[],
        )

    assert len(calls) == 1  # act only
    assert not any("reflecting" in c for c in calls)


@pytest.mark.asyncio
async def test_reflection_failure_is_swallowed():
    """A reflection failure must not break the tick."""
    agent = HumanAgent(name="Test Agent", persona=_make_persona())
    _set_plan(agent)

    def _route(**kwargs):
        system = kwargs.get("system") or ""
        if "reflecting" in system:
            return LLMResponse(content="no json here")
        return _route_by_system(**kwargs)

    with patch("emotionsim.core.config.get_settings",
               return_value=Settings(reflection_interval_steps=5)), \
         patch("emotionsim.agents.human.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_route)), \
         patch("emotionsim.agents.base.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_route)):
        result = await agent.tick(
            {"current_step": 5, "hazard_level": 5,
             "locations": {"test_location": {"nearby": []}}, "agents": {}},
            messages=[],
        )

    assert result is not None
    assert result.message.content == "The water is rising."


# ---------------------------------------------------------------------------
# Memory salience
# ---------------------------------------------------------------------------


def test_importance_weighted_recall_beats_recency():
    """High-importance old memory outranks low-importance recent memory."""
    mem = AgentMemory(agent_id="a", agent_name="A")
    mem.add_lesson("Old critical lesson about the bridge", step_index=1, importance=9)
    mem.add_lesson("Recent trivial note", step_index=20, importance=2)

    salient = mem.get_salient_memories(limit=1, current_step=21)
    assert salient[0].summary == "Old critical lesson about the bridge"

    # Recency-only selection would pick the recent one
    recency = mem.get_episodic_memories(limit=1)
    assert recency[0].summary == "Recent trivial note"


def test_salient_memories_survive_the_window():
    """Lessons live in the episodic store, not the sliding window."""
    mem = AgentMemory(agent_id="a", agent_name="A", sliding_window_size=5)
    for i in range(10):
        mem.add_event({"type": "observation", "content": f"event {i}", "step_index": i})
    mem.add_lesson("Durable lesson from step 2", step_index=2, importance=10)

    # Sliding window only kept the last 5 events — the lesson is not there
    recent = mem.get_recent_events()
    assert len(recent) == 5
    assert all("Durable lesson" not in str(e) for e in recent)

    # ...but the lesson is still recallable via salience
    assert mem.get_salient_memories(limit=1, current_step=12)[0].summary == "Durable lesson from step 2"


def test_conversation_context_uses_salience_when_step_given():
    mem = AgentMemory(agent_id="a", agent_name="A")
    mem.add_lesson("Old critical lesson about the bridge", step_index=1, importance=9)
    mem.add_lesson("Recent trivial note", step_index=20, importance=2)

    # With current_step → salience picks the old high-importance memory
    ctx = mem.get_conversation_context(max_episodic=1, current_step=21)
    assert "Old critical lesson about the bridge" in ctx
    assert "Recent trivial note" not in ctx

    # Without current_step → recency ordering (backward compatible)
    ctx_recency = mem.get_conversation_context(max_episodic=1)
    assert "Recent trivial note" in ctx_recency
    assert "Old critical lesson about the bridge" not in ctx_recency

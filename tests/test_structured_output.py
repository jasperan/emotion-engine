"""Step 3: Structured LLM output enforcement — schema validation + retry.

Covers:
- Pydantic schema validation for act / think / plan outputs
- tolerance for markdown fences / prose-wrapped JSON
- retry-once-with-feedback when validation fails
- parse-failure ~0 on valid stub responses (no spurious retries)
- cinematic fields preserved through the validated path
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from emotionsim.agents.cognitive_engine import CognitiveEngine
from emotionsim.agents.human import HumanAgent
from emotionsim.llm.base import LLMResponse
from emotionsim.llm.schemas import (
    ActResponse,
    PlanResponse,
    ThinkResponse,
    extract_json_text,
    validate_content,
)


# ---------------------------------------------------------------------------
# validate_content unit tests
# ---------------------------------------------------------------------------


def test_validate_think_valid():
    ok, parsed, err = validate_content(
        json.dumps({"urgency": "high", "assessment": "Water rising", "top_need": "shelter"}),
        ThinkResponse,
    )
    assert ok and err == ""
    assert parsed.urgency == "high"
    assert parsed.top_need == "shelter"


def test_validate_think_markdown_fence():
    ok, parsed, _ = validate_content(
        'Here is my analysis:\n```json\n{"urgency": "low", "assessment": "Calm", "top_need": "food"}\n```\nDone.',
        ThinkResponse,
    )
    assert ok
    assert parsed.urgency == "low"


def test_validate_act_cinematic_valid():
    ok, parsed, _ = validate_content(
        json.dumps({
            "action": "She grabs the rope.",
            "speech": "Hold on!",
            "thought": "We need to move.",
            "emotion": "fear",
            "move_to": "Hill",
            "stress_level": 6,
        }),
        ActResponse,
    )
    assert ok
    assert parsed.action == "She grabs the rope."
    assert parsed.speech == "Hold on!"
    assert parsed.emotion == "fear"


def test_validate_act_legacy_format_valid():
    """The legacy actions[]/message format must still validate."""
    ok, parsed, _ = validate_content(
        json.dumps({
            "actions": [{"action_type": "move", "target": "Hill", "parameters": {}}],
            "message": {"content": "I'm going", "to_target": "broadcast", "message_type": "broadcast"},
            "state_changes": {},
            "reasoning": "test",
        }),
        ActResponse,
    )
    assert ok
    assert parsed.actions[0]["action_type"] == "move"


def test_validate_think_rejects_bad_urgency():
    ok, _, err = validate_content(
        json.dumps({"urgency": "extreme", "assessment": "x", "top_need": "y"}),
        ThinkResponse,
    )
    assert not ok
    assert "urgency" in err


def test_validate_no_json():
    ok, _, err = validate_content("I think we should all evacuate now.", ThinkResponse)
    assert not ok
    assert "No JSON" in err


def test_validate_invalid_json():
    ok, _, err = validate_content('{"urgency": "high",}', ThinkResponse)
    assert not ok
    assert "Invalid JSON" in err


def test_extract_json_prose_wrapped():
    text = 'Sure, my response is: {"urgency": "high"} and that is all.'
    assert extract_json_text(text) == '{"urgency": "high"}'


# ---------------------------------------------------------------------------
# CognitiveEngine think/plan retry path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_think_retries_once_with_feedback():
    """Invalid think output → one retry with the error injected, then parse."""
    from emotionsim.schemas.persona import Persona

    engine = CognitiveEngine(persona=Persona(name="T", age=30, sex="male", occupation="W"))

    calls = []

    async def _flaky_llm(**kwargs):
        calls.append(kwargs)
        content = kwargs["messages"][-1].content
        if "failed validation" in content:
            # retry returns valid JSON
            return LLMResponse(content=json.dumps({
                "urgency": "high", "assessment": "Water rising", "top_need": "shelter",
            }))
        # first response: wrong urgency value
        return LLMResponse(content=json.dumps({
            "urgency": "extreme", "assessment": "Water rising", "top_need": "shelter",
        }))

    result = await engine.think(
        world_state="flood",
        memory_context="mem",
        recent_messages=[],
        llm_generate=_flaky_llm,
    )

    assert len(calls) == 2  # retried once
    assert "failed validation" in calls[1]["messages"][-1].content
    assert result["urgency"] == "high"  # parsed from the retry


@pytest.mark.asyncio
async def test_plan_retries_once_with_feedback():
    from emotionsim.agents.intent_memory import IntentMemory
    from emotionsim.schemas.persona import Persona

    engine = CognitiveEngine(persona=Persona(name="T", age=30, sex="male", occupation="W"))

    calls = []

    async def _flaky_llm(**kwargs):
        calls.append(kwargs)
        content = kwargs["messages"][-1].content
        if "failed validation" in content:
            return LLMResponse(content=json.dumps({
                "goal": "Reach high ground",
                "steps": ["Move to Hill", "Shelter"],
                "success_criteria": "Safe",
                "fallback": None,
            }))
        return LLMResponse(content=json.dumps({
            "goal": "Reach high ground",
            "steps": "not-a-list",  # schema violation
            "success_criteria": "Safe",
        }))

    plan = await engine.plan(
        assessment={"assessment": "rising", "urgency": "high", "top_need": "shelter"},
        intent=IntentMemory(),
        world_state="flood",
        llm_generate=_flaky_llm,
        current_step=1,
    )

    assert len(calls) == 2
    assert plan.goal == "Reach high ground"
    assert plan.steps == ["Move to Hill", "Shelter"]


# ---------------------------------------------------------------------------
# HumanAgent act retry path
# ---------------------------------------------------------------------------


def _make_persona():
    from emotionsim.schemas.persona import Persona
    return Persona(
        name="Test Agent", age=30, sex="non-binary", occupation="Tester",
        openness=5, conscientiousness=5, extraversion=5, agreeableness=5,
        neuroticism=5, risk_tolerance=5, empathy_level=5, leadership=5,
        backstory="A test agent", stress_level=3, health=10, location="test_location",
    )


@pytest.mark.asyncio
async def test_act_retries_once_on_invalid_and_preserves_cinematic():
    """First act response invalid → retry with feedback → cinematic fields kept."""
    agent = HumanAgent(name="Test Agent", persona=_make_persona())
    # Pre-set a plan so only ACT runs (1 LLM call expected, 2 with retry)
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

    calls = []

    async def _flaky_act(**kwargs):
        calls.append(kwargs)
        content = kwargs["messages"][-1].content
        if "failed validation" in content:
            return LLMResponse(content=json.dumps({
                "action": "She climbs to the hilltop.",
                "speech": "We made it!",
                "thought": "Safe now.",
                "emotion": "relief",
                "move_to": "Hill",
                "stress_level": 4,
            }))
        return LLMResponse(content='{"action": "bad, missing speech field", stress_level: 99}')

    with patch("emotionsim.agents.human.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_flaky_act)), \
         patch("emotionsim.agents.base.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_flaky_act)):
        result = await agent.tick(
            {"current_step": 1, "hazard_level": 5, "locations": {"test_location": {"nearby": ["Hill"]}}, "agents": {}},
            messages=[],
        )

    assert len(calls) == 2  # retried once
    assert "failed validation" in calls[1]["messages"][-1].content
    assert result.message is not None
    assert result.message.content == "We made it!"
    assert agent._last_cinematic["action"] == "She climbs to the hilltop."
    assert agent._last_cinematic["emotion"] == "relief"


@pytest.mark.asyncio
async def test_act_valid_response_no_retry():
    """A valid stub response parses on the first call (parse-failure ~0)."""
    agent = HumanAgent(name="Test Agent", persona=_make_persona())
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

    mock_generate = AsyncMock(side_effect=lambda **kw: LLMResponse(content=json.dumps({
        "action": "She grabs the rope.",
        "speech": "Hold on!",
        "thought": "We move now.",
        "emotion": "fear",
        "move_to": "Hill",
        "stress_level": 6,
    })))

    with patch("emotionsim.agents.human.LLMRouter.generate_with_fallback", mock_generate), \
         patch("emotionsim.agents.base.LLMRouter.generate_with_fallback", mock_generate):
        result = await agent.tick(
            {"current_step": 1, "hazard_level": 5, "locations": {"test_location": {"nearby": ["Hill"]}}, "agents": {}},
            messages=[],
        )

    assert mock_generate.await_count == 1  # no spurious retry
    assert result.message.content == "Hold on!"
    assert agent._last_cinematic["action"] == "She grabs the rope."
    assert agent._last_cinematic["emotion"] == "fear"


@pytest.mark.asyncio
async def test_act_double_failure_falls_back_to_defensive_parse():
    """If both attempts fail validation, the defensive parser still produces a response."""
    agent = HumanAgent(name="Test Agent", persona=_make_persona())
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

    async def _always_bad(**kwargs):
        return LLMResponse(content="I'm just talking, no JSON here at all.")

    with patch("emotionsim.agents.human.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_always_bad)), \
         patch("emotionsim.agents.base.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_always_bad)):
        result = await agent.tick(
            {"current_step": 1, "hazard_level": 5, "locations": {"test_location": {"nearby": ["Hill"]}}, "agents": {}},
            messages=[],
        )

    assert result is not None
    # Natural-language fallback becomes a broadcast message
    assert result.message is None or result.message.content  # not None

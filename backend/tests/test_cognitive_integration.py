"""Tests for CognitiveEngine integration into HumanAgent.tick()."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.human import HumanAgent
from app.agents.intent_memory import Plan
from app.schemas.persona import Persona
from app.llm.base import LLMResponse


def _make_persona(**overrides) -> Persona:
    defaults = dict(
        name="Test Agent",
        age=30,
        sex="male",
        occupation="Engineer",
        openness=5,
        conscientiousness=5,
        extraversion=5,
        agreeableness=5,
        neuroticism=5,
        risk_tolerance=5,
        empathy_level=5,
        leadership=5,
    )
    defaults.update(overrides)
    return Persona(**defaults)


def _make_world_state(current_step: int = 1) -> dict:
    return {
        "current_step": current_step,
        "hazard_level": 5,
        "locations": {
            "Town Square": {
                "description": "A flooded town square",
                "nearby": ["Hill", "Bridge"],
                "items": [],
            }
        },
        "agents": {},
        "objects": {},
        "events": [],
    }


def _think_response() -> LLMResponse:
    return LLMResponse(
        content=json.dumps({
            "urgency": "high",
            "assessment": "Water is rising fast",
            "top_need": "shelter",
        })
    )


def _plan_response() -> LLMResponse:
    return LLMResponse(
        content=json.dumps({
            "goal": "Reach high ground",
            "steps": ["Move to Hill", "Set up camp"],
            "success_criteria": "Safe on hilltop",
            "fallback": "Stay and wait",
        })
    )


def _act_response() -> LLMResponse:
    return LLMResponse(
        content=json.dumps({
            "actions": [{"action_type": "move", "target": "Hill", "parameters": {}}],
            "message": {"content": "I'm heading to the hill!", "to_target": "broadcast", "message_type": "broadcast"},
            "state_changes": {},
            "reasoning": "Need to get to safety",
        })
    )


class TestTickCreatesPlanOnFirstCall:
    """First tick with no plan should run THINK + PLAN + ACT (3 LLM calls)."""

    @pytest.mark.asyncio
    async def test_tick_creates_plan_on_first_call(self):
        persona = _make_persona()
        agent = HumanAgent(name="Test Agent", persona=persona)

        # Mock the LLM client to return think, plan, act responses in order
        mock_generate = AsyncMock(
            side_effect=[_think_response(), _plan_response(), _act_response()]
        )
        agent._llm_client = MagicMock()
        agent._llm_client.generate = mock_generate

        world_state = _make_world_state(current_step=1)
        result = await agent.tick(world_state, messages=[])

        # Should have called LLM 3 times: think, plan, act
        assert mock_generate.call_count == 3

        # Agent should now have a plan in intent memory
        intent = agent.agent_memory.intent
        assert intent.current_plan is not None
        assert intent.current_plan.goal == "Reach high ground"
        assert len(intent.current_plan.steps) == 2

        # Should return a valid AgentResponse with actions
        assert len(result.actions) == 1
        assert result.actions[0].action_type == "move"


class TestSecondTickReusesPlan:
    """Second tick with existing valid plan should only run ACT (1 LLM call)."""

    @pytest.mark.asyncio
    async def test_second_tick_reuses_plan(self):
        persona = _make_persona()
        agent = HumanAgent(name="Test Agent", persona=persona)

        # Pre-set a valid plan in intent memory
        plan = Plan(
            goal="Reach high ground",
            steps=["Move to Hill", "Set up camp"],
            current_step=0,
            created_at_step=1,
            success_criteria="Safe on hilltop",
            fallback="Stay and wait",
            deadline_step=20,  # Far in the future
            retry_count=0,
        )
        agent.agent_memory.intent.set_plan(plan)

        # Mock LLM - should only be called once (ACT phase)
        mock_generate = AsyncMock(return_value=_act_response())
        agent._llm_client = MagicMock()
        agent._llm_client.generate = mock_generate

        world_state = _make_world_state(current_step=2)
        result = await agent.tick(world_state, messages=[])

        # Should have called LLM only once (ACT only)
        assert mock_generate.call_count == 1

        # Plan should still exist
        assert agent.agent_memory.intent.current_plan is not None

        # Should return valid response
        assert len(result.actions) == 1

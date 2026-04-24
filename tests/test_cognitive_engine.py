"""Tests for CognitiveEngine - the think/plan/act/reflect cognitive cycle."""
import json
import pytest
from unittest.mock import AsyncMock

from emotionsim.agents.cognitive_engine import CognitiveEngine, CognitivePhase
from emotionsim.agents.intent_memory import IntentMemory, Plan
from emotionsim.agents.personality_mechanics import PersonalityMechanics
from emotionsim.schemas.persona import Persona
from emotionsim.llm.base import LLMMessage, LLMResponse


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


def _make_plan(
    current_step: int = 0,
    steps: list[str] | None = None,
    deadline_step: int | None = None,
    retry_count: int = 0,
    created_at_step: int = 0,
) -> Plan:
    return Plan(
        goal="Build a raft",
        steps=steps or ["Gather wood", "Find rope", "Assemble"],
        current_step=current_step,
        created_at_step=created_at_step,
        success_criteria="Raft is floating",
        fallback="Climb to high ground",
        deadline_step=deadline_step,
        retry_count=retry_count,
    )


class TestCognitivePhaseEnum:
    def test_enum_values(self):
        assert CognitivePhase.THINK.value == "think"
        assert CognitivePhase.PLAN.value == "plan"
        assert CognitivePhase.ACT.value == "act"


class TestDeterminePhases:
    def test_no_plan_returns_full_cycle(self):
        engine = CognitiveEngine(_make_persona())
        intent = IntentMemory()
        # No plan set
        phases = engine.determine_phases(intent, current_step=5)
        assert phases == [CognitivePhase.THINK, CognitivePhase.PLAN, CognitivePhase.ACT]

    def test_valid_plan_returns_act_only(self):
        engine = CognitiveEngine(_make_persona())
        intent = IntentMemory()
        intent.set_plan(_make_plan(current_step=0, deadline_step=20))
        phases = engine.determine_phases(intent, current_step=5)
        assert phases == [CognitivePhase.ACT]

    def test_plan_needs_replan_returns_full_cycle(self):
        engine = CognitiveEngine(_make_persona())
        intent = IntentMemory()
        # retry_count >= 3 triggers replan
        intent.set_plan(_make_plan(retry_count=3, deadline_step=20))
        phases = engine.determine_phases(intent, current_step=5)
        assert phases == [CognitivePhase.THINK, CognitivePhase.PLAN, CognitivePhase.ACT]

    def test_deadline_exceeded_returns_full_cycle(self):
        engine = CognitiveEngine(_make_persona())
        intent = IntentMemory()
        intent.set_plan(_make_plan(deadline_step=10))
        phases = engine.determine_phases(intent, current_step=15)
        assert phases == [CognitivePhase.THINK, CognitivePhase.PLAN, CognitivePhase.ACT]

    def test_plan_steps_completed_returns_full_cycle(self):
        engine = CognitiveEngine(_make_persona())
        intent = IntentMemory()
        # current_step >= len(steps) means plan is complete, needs replan
        intent.set_plan(_make_plan(current_step=3, steps=["a", "b", "c"], deadline_step=20))
        phases = engine.determine_phases(intent, current_step=5)
        assert phases == [CognitivePhase.THINK, CognitivePhase.PLAN, CognitivePhase.ACT]


class TestThink:
    @pytest.mark.asyncio
    async def test_returns_assessment_dict(self):
        engine = CognitiveEngine(_make_persona())
        llm_response = LLMResponse(
            content=json.dumps({
                "urgency": "medium",
                "assessment": "Water is rising slowly",
                "top_need": "shelter",
            })
        )
        mock_generate = AsyncMock(return_value=llm_response)

        result = await engine.think(
            world_state="Flood water at 2m",
            memory_context="I saw a hill nearby",
            recent_messages=["Agent B: We need to move!"],
            llm_generate=mock_generate,
        )
        assert result["urgency"] in ("high", "medium", "low")
        assert "assessment" in result
        assert "top_need" in result
        mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_urgency_modifier_applied_high_neuroticism(self):
        """High neuroticism should bump urgency up."""
        engine = CognitiveEngine(_make_persona(neuroticism=9))
        llm_response = LLMResponse(
            content=json.dumps({
                "urgency": "medium",
                "assessment": "Situation seems okay",
                "top_need": "food",
            })
        )
        mock_generate = AsyncMock(return_value=llm_response)

        result = await engine.think(
            world_state="Normal conditions",
            memory_context="",
            recent_messages=[],
            llm_generate=mock_generate,
        )
        # neuroticism=9 -> modifier=+2, medium should bump to high
        assert result["urgency"] == "high"

    @pytest.mark.asyncio
    async def test_urgency_modifier_applied_low_neuroticism(self):
        """Low neuroticism should lower urgency."""
        engine = CognitiveEngine(_make_persona(neuroticism=1))
        llm_response = LLMResponse(
            content=json.dumps({
                "urgency": "medium",
                "assessment": "Things are bad",
                "top_need": "shelter",
            })
        )
        mock_generate = AsyncMock(return_value=llm_response)

        result = await engine.think(
            world_state="Flood",
            memory_context="",
            recent_messages=[],
            llm_generate=mock_generate,
        )
        # neuroticism=1 -> modifier=-2, medium should drop to low
        assert result["urgency"] == "low"

    @pytest.mark.asyncio
    async def test_fallback_on_bad_json(self):
        """If LLM returns invalid JSON, should fall back to defaults."""
        engine = CognitiveEngine(_make_persona())
        llm_response = LLMResponse(content="This is not JSON at all")
        mock_generate = AsyncMock(return_value=llm_response)

        result = await engine.think(
            world_state="Flood",
            memory_context="",
            recent_messages=[],
            llm_generate=mock_generate,
        )
        assert "urgency" in result
        assert "assessment" in result
        assert "top_need" in result

    @pytest.mark.asyncio
    async def test_think_prompt_includes_personality(self):
        """System prompt should include personality-based additions."""
        engine = CognitiveEngine(_make_persona(openness=8, neuroticism=8))
        llm_response = LLMResponse(
            content=json.dumps({
                "urgency": "low",
                "assessment": "ok",
                "top_need": "water",
            })
        )
        mock_generate = AsyncMock(return_value=llm_response)

        await engine.think(
            world_state="Flood",
            memory_context="",
            recent_messages=[],
            llm_generate=mock_generate,
        )
        # Verify call was made with messages containing personality text
        call_kwargs = mock_generate.call_args
        messages = call_kwargs[1].get("messages") or call_kwargs[0][0]
        system_msg = next(m for m in messages if m.role == "system")
        assert "creative" in system_msg.content.lower() or "unconventional" in system_msg.content.lower()


class TestPlan:
    @pytest.mark.asyncio
    async def test_creates_plan_with_correct_constraints(self):
        engine = CognitiveEngine(_make_persona(conscientiousness=8))
        llm_response = LLMResponse(
            content=json.dumps({
                "goal": "Reach high ground",
                "steps": ["Pack supplies", "Cross bridge", "Climb hill", "Set up camp", "Signal rescue", "Extra step"],
                "success_criteria": "Safe on hilltop",
                "fallback": "Stay and wait",
            })
        )
        mock_generate = AsyncMock(return_value=llm_response)

        intent = IntentMemory()
        assessment = {"urgency": "high", "assessment": "Water rising", "top_need": "safety"}

        plan = await engine.plan(
            assessment=assessment,
            intent=intent,
            world_state="Flood",
            llm_generate=mock_generate,
            current_step=10,
        )
        # conscientiousness=8 -> max_plan_steps=5, so 6 steps should be capped
        assert len(plan.steps) <= 5
        assert plan.current_step == 0
        assert plan.created_at_step == 10
        assert plan.deadline_step is not None

    @pytest.mark.asyncio
    async def test_plan_deadline_uses_personality(self):
        persona = _make_persona(neuroticism=9, conscientiousness=3)
        engine = CognitiveEngine(persona)
        mechanics = PersonalityMechanics(persona)
        expected_patience = mechanics.deadline_patience()

        llm_response = LLMResponse(
            content=json.dumps({
                "goal": "Escape",
                "steps": ["Run"],
                "success_criteria": "Escaped",
                "fallback": None,
            })
        )
        mock_generate = AsyncMock(return_value=llm_response)
        intent = IntentMemory()
        assessment = {"urgency": "high", "assessment": "Danger", "top_need": "safety"}

        plan = await engine.plan(
            assessment=assessment,
            intent=intent,
            world_state="Fire",
            llm_generate=mock_generate,
            current_step=5,
        )
        assert plan.deadline_step == 5 + expected_patience

    @pytest.mark.asyncio
    async def test_plan_includes_blocked_actions(self):
        engine = CognitiveEngine(_make_persona())
        llm_response = LLMResponse(
            content=json.dumps({
                "goal": "Find shelter",
                "steps": ["Go north"],
                "success_criteria": "In shelter",
                "fallback": None,
            })
        )
        mock_generate = AsyncMock(return_value=llm_response)
        intent = IntentMemory()
        intent.add_blocked_action("cross river", "bridge broken", step=3)
        assessment = {"urgency": "medium", "assessment": "Need shelter", "top_need": "shelter"}

        await engine.plan(
            assessment=assessment,
            intent=intent,
            world_state="Rain",
            llm_generate=mock_generate,
            current_step=5,
        )
        # Check that blocked actions are included in the prompt
        call_kwargs = mock_generate.call_args
        messages = call_kwargs[1].get("messages") or call_kwargs[0][0]
        all_content = " ".join(m.content for m in messages)
        assert "cross river" in all_content

    @pytest.mark.asyncio
    async def test_plan_fallback_on_bad_json(self):
        engine = CognitiveEngine(_make_persona())
        llm_response = LLMResponse(content="Not valid JSON")
        mock_generate = AsyncMock(return_value=llm_response)
        intent = IntentMemory()
        assessment = {"urgency": "high", "assessment": "Danger", "top_need": "safety"}

        plan = await engine.plan(
            assessment=assessment,
            intent=intent,
            world_state="Flood",
            llm_generate=mock_generate,
            current_step=5,
        )
        # Should return a fallback plan
        assert isinstance(plan, Plan)
        assert len(plan.steps) > 0


class TestReflect:
    def test_no_plan_returns_early(self):
        engine = CognitiveEngine(_make_persona())
        intent = IntentMemory()
        # Should not raise
        engine.reflect(intent, actions_taken=["move_north"], current_step=5)
        assert intent.current_plan is None

    def test_advances_on_nontrivial_action(self):
        engine = CognitiveEngine(_make_persona())
        intent = IntentMemory()
        intent.set_plan(_make_plan(current_step=0, retry_count=1))
        engine.reflect(intent, actions_taken=["move_north"], current_step=5)
        assert intent.current_plan.current_step == 1
        assert intent.current_plan.retry_count == 0

    def test_increments_retry_on_wait_only(self):
        engine = CognitiveEngine(_make_persona())
        intent = IntentMemory()
        intent.set_plan(_make_plan(current_step=0, retry_count=0))
        engine.reflect(intent, actions_taken=["wait"], current_step=5)
        assert intent.current_plan.retry_count == 1
        assert intent.current_plan.current_step == 0

    def test_increments_retry_on_speak_only(self):
        engine = CognitiveEngine(_make_persona())
        intent = IntentMemory()
        intent.set_plan(_make_plan(current_step=0, retry_count=0))
        engine.reflect(intent, actions_taken=["speak"], current_step=5)
        assert intent.current_plan.retry_count == 1

    def test_completes_plan_on_all_steps_done(self):
        engine = CognitiveEngine(_make_persona())
        intent = IntentMemory()
        # Plan with 3 steps, agent is on step 2 (last one, 0-indexed)
        intent.set_plan(_make_plan(current_step=2, steps=["a", "b", "c"]))
        engine.reflect(intent, actions_taken=["build_raft"], current_step=10)
        # After advancing, current_step=3 >= len(steps)=3 -> plan complete
        assert intent.current_plan is None
        assert len(intent.completed_plans) == 1
        assert intent.completed_plans[0].outcome == "success"

    def test_completes_plan_on_retry_threshold(self):
        persona = _make_persona(neuroticism=5)
        engine = CognitiveEngine(persona)
        mechanics = PersonalityMechanics(persona)
        threshold = mechanics.replan_threshold()

        intent = IntentMemory()
        intent.set_plan(_make_plan(current_step=0, retry_count=threshold - 1))
        engine.reflect(intent, actions_taken=["wait"], current_step=5)
        # retry_count should now equal threshold -> plan failed
        assert intent.current_plan is None
        assert len(intent.completed_plans) == 1
        assert intent.completed_plans[0].outcome == "failed"

    def test_nontrivial_action_mixed_with_wait(self):
        """If actions include both wait and a real action, it counts as nontrivial."""
        engine = CognitiveEngine(_make_persona())
        intent = IntentMemory()
        intent.set_plan(_make_plan(current_step=0))
        engine.reflect(intent, actions_taken=["wait", "move_north"], current_step=5)
        assert intent.current_plan.current_step == 1
        assert intent.current_plan.retry_count == 0

    def test_empty_actions_increments_retry(self):
        engine = CognitiveEngine(_make_persona())
        intent = IntentMemory()
        intent.set_plan(_make_plan(current_step=0, retry_count=0))
        engine.reflect(intent, actions_taken=[], current_step=5)
        assert intent.current_plan.retry_count == 1

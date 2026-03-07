import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.cognitive_engine_v2 import CognitiveEngineV2, CognitivePhaseV2, CycleResult
from app.agents.intent_memory import IntentMemory, Plan
from app.simulation.goal_tree import GoalTree, GoalLevel, GoalStatus
from app.simulation.governance import GovernanceGate, GovernanceConfig, GateStatus
from app.agents.personality_mechanics import PersonalityMechanics


def _make_persona(neuroticism=5, conscientiousness=5, openness=5,
                  extraversion=5, agreeableness=5, risk_tolerance=5,
                  empathy_level=5, leadership=5):
    p = MagicMock()
    p.neuroticism = neuroticism
    p.conscientiousness = conscientiousness
    p.openness = openness
    p.extraversion = extraversion
    p.agreeableness = agreeableness
    p.risk_tolerance = risk_tolerance
    p.empathy_level = empathy_level
    p.leadership = leadership
    return p


def _make_goal_tree():
    tree = GoalTree()
    tree.set_mission("Ensure maximum survival", step=0)
    gid = tree.add_group_goal("Evacuate basement", ["a1"], step=1)
    tree.add_agent_goal("Find rope", "a1", gid, step=2, priority=7)
    return tree


class TestCognitivePhaseV2:
    def test_all_phases_present(self):
        phases = list(CognitivePhaseV2)
        assert len(phases) == 7
        assert CognitivePhaseV2.ALIGN_GOALS in phases
        assert CognitivePhaseV2.GOVERNANCE_CHECK in phases
        assert CognitivePhaseV2.UPDATE_GOALS in phases


class TestDeterminePhases:
    def test_full_replan_when_no_plan(self):
        engine = CognitiveEngineV2(_make_persona())
        intent = IntentMemory()
        phases = engine.determine_phases(intent, _make_goal_tree(), current_step=1)
        assert CognitivePhaseV2.THINK in phases
        assert CognitivePhaseV2.ALIGN_GOALS in phases
        assert CognitivePhaseV2.PLAN in phases
        assert CognitivePhaseV2.GOVERNANCE_CHECK in phases
        assert CognitivePhaseV2.ACT in phases
        assert CognitivePhaseV2.REFLECT in phases
        assert CognitivePhaseV2.UPDATE_GOALS in phases

    def test_short_cycle_with_active_plan(self):
        engine = CognitiveEngineV2(_make_persona())
        intent = IntentMemory()
        intent.set_plan(Plan(
            goal="Find rope",
            steps=["Go to storage", "Get rope"],
            current_step=0,
            created_at_step=1,
            success_criteria="Have rope",
            fallback=None,
            deadline_step=20,
            retry_count=0,
        ))
        phases = engine.determine_phases(intent, _make_goal_tree(), current_step=2)
        assert CognitivePhaseV2.THINK not in phases
        assert CognitivePhaseV2.GOVERNANCE_CHECK in phases
        assert CognitivePhaseV2.ACT in phases
        assert CognitivePhaseV2.UPDATE_GOALS in phases


class TestAlignGoals:
    def test_selects_highest_priority_goal(self):
        engine = CognitiveEngineV2(_make_persona())
        tree = _make_goal_tree()
        gid = list(tree._goals.values())[1].id  # group goal
        tree.add_agent_goal("Lower priority", "a1", gid, step=3, priority=3)
        result = engine.align_goals("a1", tree)
        assert result["selected_goal"].priority == 7

    def test_returns_none_when_no_goals(self):
        engine = CognitiveEngineV2(_make_persona())
        tree = GoalTree()
        tree.set_mission("Survive", step=0)
        result = engine.align_goals("a1", tree)
        assert result["selected_goal"] is None
        assert result["needs_new_goal"] is True

    def test_includes_goal_context(self):
        engine = CognitiveEngineV2(_make_persona())
        tree = _make_goal_tree()
        result = engine.align_goals("a1", tree)
        assert "goal_context" in result
        assert "Find rope" in result["goal_context"]


class TestGovernanceCheck:
    def test_benign_action_passes(self):
        engine = CognitiveEngineV2(_make_persona())
        gate = GovernanceGate(GovernanceConfig())
        result = engine.governance_check(
            agent_id="a1",
            action="Walk to kitchen",
            reasoning="Need supplies",
            step=5,
            gate=gate,
        )
        assert result["passed"] is True
        assert result["paused"] is False

    def test_ethical_action_pauses(self):
        engine = CognitiveEngineV2(_make_persona())
        gate = GovernanceGate(GovernanceConfig())
        result = engine.governance_check(
            agent_id="a1",
            action="I'm abandoning the injured child",
            reasoning="Self-preservation",
            step=5,
            gate=gate,
        )
        assert result["passed"] is False
        assert result["paused"] is True

    def test_governance_disabled_always_passes(self):
        engine = CognitiveEngineV2(_make_persona())
        result = engine.governance_check(
            agent_id="a1",
            action="Abandon everyone",
            reasoning="Fear",
            step=5,
            gate=None,
        )
        assert result["passed"] is True


class TestUpdateGoals:
    def test_update_goals_recalculates_priorities(self):
        engine = CognitiveEngineV2(_make_persona())
        tree = _make_goal_tree()
        agent_goal_id = [g.id for g in tree.get_agent_goals("a1")][0]
        tree.complete_goal(agent_goal_id, step=5)
        engine.update_goals(tree, step=5)
        group_goals = [g for g in tree._goals.values() if g.level == GoalLevel.GROUP]
        assert group_goals[0].status == GoalStatus.COMPLETED

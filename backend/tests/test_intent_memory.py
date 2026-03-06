"""Tests for IntentMemory (Tier 4) - plans, commitments, blocked actions"""
import pytest
from app.agents.intent_memory import (
    IntentMemory,
    Plan,
    Commitment,
    BlockedAction,
    CompletedPlan,
)
from app.agents.memory import AgentMemory


class TestPlanDataclass:
    def test_plan_creation(self):
        plan = Plan(
            goal="Build a raft",
            steps=["Gather wood", "Find rope", "Assemble raft"],
            current_step=0,
            created_at_step=5,
            success_criteria="Raft is floating",
            fallback="Climb to high ground",
            deadline_step=20,
            retry_count=0,
        )
        assert plan.goal == "Build a raft"
        assert len(plan.steps) == 3
        assert plan.current_step == 0
        assert plan.created_at_step == 5
        assert plan.deadline_step == 20
        assert plan.retry_count == 0

    def test_plan_to_dict(self):
        plan = Plan(
            goal="Evacuate",
            steps=["Alert others", "Move to hill"],
            current_step=1,
            created_at_step=3,
            success_criteria="Everyone safe",
            fallback=None,
            deadline_step=None,
            retry_count=0,
        )
        d = plan.to_dict()
        assert d["goal"] == "Evacuate"
        assert d["steps"] == ["Alert others", "Move to hill"]
        assert d["current_step"] == 1
        assert d["fallback"] is None

    def test_plan_from_dict(self):
        data = {
            "goal": "Find shelter",
            "steps": ["Look around", "Go there"],
            "current_step": 0,
            "created_at_step": 1,
            "success_criteria": "In shelter",
            "fallback": "Stay put",
            "deadline_step": 10,
            "retry_count": 2,
        }
        plan = Plan.from_dict(data)
        assert plan.goal == "Find shelter"
        assert plan.retry_count == 2

    def test_plan_roundtrip(self):
        plan = Plan(
            goal="Test",
            steps=["a", "b"],
            current_step=1,
            created_at_step=0,
            success_criteria="done",
            fallback="stop",
            deadline_step=50,
            retry_count=1,
        )
        restored = Plan.from_dict(plan.to_dict())
        assert restored.goal == plan.goal
        assert restored.steps == plan.steps
        assert restored.current_step == plan.current_step
        assert restored.deadline_step == plan.deadline_step


class TestCommitmentDataclass:
    def test_creation(self):
        c = Commitment(to="agent_2", what="Bring supplies", step=10)
        assert c.to == "agent_2"
        assert c.what == "Bring supplies"
        assert c.step == 10

    def test_to_dict_from_dict(self):
        c = Commitment(to="agent_3", what="Guard the camp", step=5)
        restored = Commitment.from_dict(c.to_dict())
        assert restored.to == c.to
        assert restored.what == c.what
        assert restored.step == c.step


class TestBlockedActionDataclass:
    def test_creation(self):
        ba = BlockedAction(action="cross_river", reason="Water too deep", step=7)
        assert ba.action == "cross_river"
        assert ba.reason == "Water too deep"

    def test_to_dict_from_dict(self):
        ba = BlockedAction(action="open_door", reason="Locked", step=3)
        restored = BlockedAction.from_dict(ba.to_dict())
        assert restored.action == ba.action
        assert restored.reason == ba.reason
        assert restored.step == ba.step


class TestCompletedPlanDataclass:
    def test_creation(self):
        cp = CompletedPlan(
            goal="Build raft",
            outcome="success",
            reason="Raft completed",
            steps_taken=5,
        )
        assert cp.outcome == "success"
        assert cp.steps_taken == 5

    def test_outcome_values(self):
        for outcome in ("success", "failed", "abandoned"):
            cp = CompletedPlan(goal="x", outcome=outcome, reason="r", steps_taken=1)
            assert cp.outcome == outcome

    def test_to_dict_from_dict(self):
        cp = CompletedPlan(goal="g", outcome="failed", reason="no materials", steps_taken=3)
        restored = CompletedPlan.from_dict(cp.to_dict())
        assert restored.goal == cp.goal
        assert restored.outcome == cp.outcome
        assert restored.steps_taken == cp.steps_taken


class TestIntentMemory:
    def make_plan(self, **kwargs):
        defaults = dict(
            goal="Build a raft",
            steps=["Gather wood", "Find rope", "Assemble"],
            current_step=0,
            created_at_step=1,
            success_criteria="Raft built",
            fallback=None,
            deadline_step=None,
            retry_count=0,
        )
        defaults.update(kwargs)
        return Plan(**defaults)

    def test_initial_state(self):
        im = IntentMemory()
        assert im.current_plan is None
        assert im.commitments == []
        assert im.completed_plans == []
        assert im.blocked_actions == []

    def test_set_plan(self):
        im = IntentMemory()
        plan = self.make_plan()
        im.set_plan(plan)
        assert im.current_plan is plan
        assert im.current_plan.goal == "Build a raft"

    def test_set_plan_replaces_existing(self):
        im = IntentMemory()
        im.set_plan(self.make_plan(goal="Plan A"))
        im.set_plan(self.make_plan(goal="Plan B"))
        assert im.current_plan.goal == "Plan B"

    def test_advance_plan_step(self):
        im = IntentMemory()
        im.set_plan(self.make_plan())
        assert im.current_plan.current_step == 0
        im.advance_plan_step()
        assert im.current_plan.current_step == 1
        im.advance_plan_step()
        assert im.current_plan.current_step == 2

    def test_advance_plan_step_no_plan(self):
        im = IntentMemory()
        # Should not raise
        im.advance_plan_step()

    def test_complete_plan_success(self):
        im = IntentMemory()
        im.set_plan(self.make_plan())
        im.advance_plan_step()
        im.complete_plan("success", "All done")
        assert im.current_plan is None
        assert len(im.completed_plans) == 1
        assert im.completed_plans[0].outcome == "success"
        assert im.completed_plans[0].reason == "All done"
        assert im.completed_plans[0].steps_taken == 1

    def test_complete_plan_failed(self):
        im = IntentMemory()
        im.set_plan(self.make_plan())
        im.advance_plan_step()
        im.advance_plan_step()
        im.complete_plan("failed", "No materials")
        assert im.current_plan is None
        assert im.completed_plans[0].outcome == "failed"
        assert im.completed_plans[0].steps_taken == 2

    def test_complete_plan_no_plan(self):
        im = IntentMemory()
        # Should not raise
        im.complete_plan("abandoned", "Nothing to do")
        assert len(im.completed_plans) == 0

    def test_completed_plans_capped_at_5(self):
        im = IntentMemory()
        for i in range(7):
            im.set_plan(self.make_plan(goal=f"Plan {i}"))
            im.complete_plan("success", f"Done {i}")
        assert len(im.completed_plans) == 5
        # Should keep the most recent 5
        assert im.completed_plans[-1].goal == "Plan 6"

    def test_add_commitment(self):
        im = IntentMemory()
        im.add_commitment("agent_2", "Bring water", 5)
        assert len(im.commitments) == 1
        assert im.commitments[0].to == "agent_2"
        assert im.commitments[0].what == "Bring water"
        assert im.commitments[0].step == 5

    def test_commitments_capped_at_10(self):
        im = IntentMemory()
        for i in range(12):
            im.add_commitment(f"agent_{i}", f"Task {i}", i)
        assert len(im.commitments) == 10
        # Should keep most recent
        assert im.commitments[-1].to == "agent_11"

    def test_add_blocked_action(self):
        im = IntentMemory()
        im.add_blocked_action("cross_river", "Too deep", 3)
        assert len(im.blocked_actions) == 1
        assert im.blocked_actions[0].action == "cross_river"

    def test_blocked_actions_capped_at_20(self):
        im = IntentMemory()
        for i in range(22):
            im.add_blocked_action(f"action_{i}", f"reason_{i}", i)
        assert len(im.blocked_actions) == 20
        assert im.blocked_actions[-1].action == "action_21"

    def test_is_action_blocked(self):
        im = IntentMemory()
        im.add_blocked_action("cross_river", "Too deep", 3)
        assert im.is_action_blocked("cross_river") is True
        assert im.is_action_blocked("build_raft") is False

    def test_plan_needs_replan_no_plan(self):
        im = IntentMemory()
        assert im.plan_needs_replan(10) is True

    def test_plan_needs_replan_retry_exceeded(self):
        im = IntentMemory()
        im.set_plan(self.make_plan(retry_count=3))
        assert im.plan_needs_replan(10) is True

    def test_plan_needs_replan_plan_complete(self):
        im = IntentMemory()
        plan = self.make_plan(steps=["a", "b"])
        plan.current_step = 2  # past all steps
        im.set_plan(plan)
        assert im.plan_needs_replan(10) is True

    def test_plan_needs_replan_valid_plan(self):
        im = IntentMemory()
        im.set_plan(self.make_plan(retry_count=0))
        assert im.plan_needs_replan(10) is False

    def test_plan_deadline_exceeded(self):
        im = IntentMemory()
        im.set_plan(self.make_plan(deadline_step=15))
        assert im.plan_deadline_exceeded(10) is False
        assert im.plan_deadline_exceeded(15) is True
        assert im.plan_deadline_exceeded(20) is True

    def test_plan_deadline_exceeded_no_deadline(self):
        im = IntentMemory()
        im.set_plan(self.make_plan(deadline_step=None))
        assert im.plan_deadline_exceeded(100) is False

    def test_plan_deadline_exceeded_no_plan(self):
        im = IntentMemory()
        assert im.plan_deadline_exceeded(10) is False

    def test_get_context_string_empty(self):
        im = IntentMemory()
        ctx = im.get_context_string()
        assert isinstance(ctx, str)

    def test_get_context_string_with_plan(self):
        im = IntentMemory()
        im.set_plan(self.make_plan(goal="Build a raft", steps=["Gather wood", "Find rope", "Assemble"]))
        ctx = im.get_context_string()
        assert "Build a raft" in ctx
        assert "Gather wood" in ctx

    def test_get_context_string_with_commitments(self):
        im = IntentMemory()
        im.add_commitment("Maria", "Bring water", 5)
        ctx = im.get_context_string()
        assert "Maria" in ctx
        assert "Bring water" in ctx

    def test_get_context_string_with_blocked(self):
        im = IntentMemory()
        im.add_blocked_action("cross_river", "Too deep", 3)
        ctx = im.get_context_string()
        assert "cross_river" in ctx

    def test_to_dict_empty(self):
        im = IntentMemory()
        d = im.to_dict()
        assert d["current_plan"] is None
        assert d["commitments"] == []
        assert d["completed_plans"] == []
        assert d["blocked_actions"] == []

    def test_to_dict_populated(self):
        im = IntentMemory()
        im.set_plan(self.make_plan())
        im.add_commitment("agent_2", "Help", 1)
        im.add_blocked_action("fly", "Can't fly", 2)
        d = im.to_dict()
        assert d["current_plan"]["goal"] == "Build a raft"
        assert len(d["commitments"]) == 1
        assert len(d["blocked_actions"]) == 1

    def test_from_dict_empty(self):
        im = IntentMemory.from_dict({})
        assert im.current_plan is None
        assert im.commitments == []

    def test_roundtrip_serialization(self):
        im = IntentMemory()
        im.set_plan(self.make_plan(goal="Survive"))
        im.add_commitment("Bob", "Share food", 3)
        im.add_blocked_action("swim", "No skill", 4)
        im.advance_plan_step()
        im.complete_plan("success", "Survived")
        im.set_plan(self.make_plan(goal="Rebuild"))

        d = im.to_dict()
        restored = IntentMemory.from_dict(d)

        assert restored.current_plan.goal == "Rebuild"
        assert len(restored.completed_plans) == 1
        assert restored.completed_plans[0].goal == "Survive"
        assert len(restored.commitments) == 1
        assert len(restored.blocked_actions) == 1


class TestAgentMemoryIntentIntegration:
    """Test IntentMemory integration into AgentMemory"""

    def test_agent_memory_has_intent(self):
        mem = AgentMemory(agent_id="a1", agent_name="Alice")
        assert hasattr(mem, "intent")
        assert isinstance(mem.intent, IntentMemory)

    def test_intent_in_conversation_context(self):
        mem = AgentMemory(agent_id="a1", agent_name="Alice")
        mem.intent.set_plan(Plan(
            goal="Find shelter",
            steps=["Look around", "Go there"],
            current_step=0,
            created_at_step=1,
            success_criteria="In shelter",
            fallback=None,
            deadline_step=None,
            retry_count=0,
        ))
        ctx = mem.get_conversation_context()
        assert "Find shelter" in ctx

    def test_intent_in_to_dict(self):
        mem = AgentMemory(agent_id="a1", agent_name="Alice")
        mem.intent.add_commitment("Bob", "Help", 1)
        d = mem.to_dict()
        assert "intent" in d
        assert len(d["intent"]["commitments"]) == 1

    def test_intent_in_from_dict(self):
        mem = AgentMemory(agent_id="a1", agent_name="Alice")
        mem.intent.set_plan(Plan(
            goal="Escape",
            steps=["Run"],
            current_step=0,
            created_at_step=0,
            success_criteria="Safe",
            fallback=None,
            deadline_step=None,
            retry_count=0,
        ))
        mem.intent.add_commitment("Eve", "Wait", 2)

        d = mem.to_dict()
        restored = AgentMemory.from_dict(d)
        assert isinstance(restored.intent, IntentMemory)
        assert restored.intent.current_plan.goal == "Escape"
        assert len(restored.intent.commitments) == 1

    def test_clear_resets_intent(self):
        mem = AgentMemory(agent_id="a1", agent_name="Alice")
        mem.intent.set_plan(Plan(
            goal="Test",
            steps=["a"],
            current_step=0,
            created_at_step=0,
            success_criteria="done",
            fallback=None,
            deadline_step=None,
            retry_count=0,
        ))
        mem.clear()
        assert mem.intent.current_plan is None
        assert mem.intent.commitments == []
        assert mem.intent.blocked_actions == []
        assert mem.intent.completed_plans == []

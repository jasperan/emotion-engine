"""Tests for PersonalityMechanics — TDD approach with two contrasting personas."""
import pytest

from app.schemas.persona import Persona
from app.agents.personality_mechanics import PersonalityMechanics


@pytest.fixture
def cautious_persona() -> Persona:
    return Persona(
        name="Elder",
        age=65,
        sex="male",
        occupation="retired teacher",
        openness=3,
        conscientiousness=9,
        extraversion=3,
        agreeableness=7,
        neuroticism=8,
        risk_tolerance=2,
        empathy_level=8,
        leadership=4,
    )


@pytest.fixture
def bold_persona() -> Persona:
    return Persona(
        name="Scout",
        age=22,
        sex="female",
        occupation="firefighter",
        openness=8,
        conscientiousness=4,
        extraversion=8,
        agreeableness=4,
        neuroticism=2,
        risk_tolerance=9,
        empathy_level=5,
        leadership=8,
    )


# ── THINK phase ──────────────────────────────────────────────────────────


class TestUrgencyModifier:
    def test_high_neuroticism_positive(self, cautious_persona):
        pm = PersonalityMechanics(cautious_persona)
        # round((8 - 5) * 0.5) = round(1.5) = 2
        assert pm.urgency_modifier() == 2

    def test_low_neuroticism_negative(self, bold_persona):
        pm = PersonalityMechanics(bold_persona)
        # round((2 - 5) * 0.5) = round(-1.5) = -2
        assert pm.urgency_modifier() == -2

    def test_neutral_neuroticism(self):
        p = Persona(name="Mid", age=30, sex="non-binary", occupation="clerk", neuroticism=5)
        assert PersonalityMechanics(p).urgency_modifier() == 0

    def test_range_bounds(self):
        low = Persona(name="L", age=20, sex="male", occupation="x", neuroticism=1)
        high = Persona(name="H", age=20, sex="male", occupation="x", neuroticism=10)
        assert PersonalityMechanics(low).urgency_modifier() == -2
        assert PersonalityMechanics(high).urgency_modifier() == 2


class TestIncludeNovelOptions:
    def test_low_openness_false(self, cautious_persona):
        assert PersonalityMechanics(cautious_persona).include_novel_options() is False

    def test_high_openness_true(self, bold_persona):
        assert PersonalityMechanics(bold_persona).include_novel_options() is True

    def test_boundary_six(self):
        p = Persona(name="B", age=30, sex="male", occupation="x", openness=6)
        assert PersonalityMechanics(p).include_novel_options() is True

    def test_boundary_five(self):
        p = Persona(name="B", age=30, sex="male", occupation="x", openness=5)
        assert PersonalityMechanics(p).include_novel_options() is False


class TestThinkPromptAdditions:
    def test_returns_string(self, cautious_persona):
        text = PersonalityMechanics(cautious_persona).think_prompt_additions()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_differs_between_personas(self, cautious_persona, bold_persona):
        t1 = PersonalityMechanics(cautious_persona).think_prompt_additions()
        t2 = PersonalityMechanics(bold_persona).think_prompt_additions()
        assert t1 != t2


# ── PLAN phase ───────────────────────────────────────────────────────────


class TestMaxPlanSteps:
    def test_high_conscientiousness(self, cautious_persona):
        # conscientiousness=9 -> >=8 -> 5
        assert PersonalityMechanics(cautious_persona).max_plan_steps() == 5

    def test_low_conscientiousness(self, bold_persona):
        # conscientiousness=4 -> >=4 -> 2
        assert PersonalityMechanics(bold_persona).max_plan_steps() == 2

    def test_boundary_eight(self):
        p = Persona(name="B", age=30, sex="male", occupation="x", conscientiousness=8)
        assert PersonalityMechanics(p).max_plan_steps() == 5

    def test_boundary_six(self):
        p = Persona(name="B", age=30, sex="male", occupation="x", conscientiousness=6)
        assert PersonalityMechanics(p).max_plan_steps() == 3

    def test_very_low(self):
        p = Persona(name="B", age=30, sex="male", occupation="x", conscientiousness=2)
        assert PersonalityMechanics(p).max_plan_steps() == 1


class TestDeadlinePatience:
    def test_cautious(self, cautious_persona):
        pm = PersonalityMechanics(cautious_persona)
        # base=5, neuro_mod=-(8-5)=-3, consc_mod=(9-5)*0.5=2.0
        # total = 5 + (-3) + 2.0 = 4.0 -> int 4
        assert pm.deadline_patience() == 4

    def test_bold(self, bold_persona):
        pm = PersonalityMechanics(bold_persona)
        # base=5, neuro_mod=-(2-5)=3, consc_mod=(4-5)*0.5=-0.5
        # total = 5 + 3 + (-0.5) = 7.5 -> int 7
        assert pm.deadline_patience() == 7

    def test_minimum_two(self):
        p = Persona(name="X", age=30, sex="male", occupation="x", neuroticism=10, conscientiousness=1)
        # base=5, neuro_mod=-(10-5)=-5, consc_mod=(1-5)*0.5=-2
        # total = 5 + (-5) + (-2) = -2 -> clamped to 2
        assert PersonalityMechanics(p).deadline_patience() == 2


class TestAllowedRiskLevel:
    def test_cautious(self, cautious_persona):
        assert PersonalityMechanics(cautious_persona).allowed_risk_level() == "low"

    def test_bold(self, bold_persona):
        assert PersonalityMechanics(bold_persona).allowed_risk_level() == "high"

    def test_medium(self):
        p = Persona(name="M", age=30, sex="male", occupation="x", risk_tolerance=5)
        assert PersonalityMechanics(p).allowed_risk_level() == "medium"

    def test_boundary_seven(self):
        p = Persona(name="M", age=30, sex="male", occupation="x", risk_tolerance=7)
        assert PersonalityMechanics(p).allowed_risk_level() == "high"

    def test_boundary_four(self):
        p = Persona(name="M", age=30, sex="male", occupation="x", risk_tolerance=4)
        assert PersonalityMechanics(p).allowed_risk_level() == "medium"


class TestCoordinationStyle:
    def test_cautious(self, cautious_persona):
        # leadership=4 -> collaborator
        assert PersonalityMechanics(cautious_persona).coordination_style() == "collaborator"

    def test_bold(self, bold_persona):
        # leadership=8 -> leader
        assert PersonalityMechanics(bold_persona).coordination_style() == "leader"

    def test_solo(self):
        p = Persona(name="S", age=30, sex="male", occupation="x", leadership=2)
        assert PersonalityMechanics(p).coordination_style() == "solo"


class TestPlanConstraintsText:
    def test_returns_string(self, cautious_persona):
        text = PersonalityMechanics(cautious_persona).plan_constraints_text()
        assert isinstance(text, str)
        assert len(text) > 0

    def test_differs_between_personas(self, cautious_persona, bold_persona):
        t1 = PersonalityMechanics(cautious_persona).plan_constraints_text()
        t2 = PersonalityMechanics(bold_persona).plan_constraints_text()
        assert t1 != t2


# ── ACT phase ────────────────────────────────────────────────────────────


class TestCommunicationLevel:
    def test_cautious(self, cautious_persona):
        assert PersonalityMechanics(cautious_persona).communication_level() == "minimal"

    def test_bold(self, bold_persona):
        assert PersonalityMechanics(bold_persona).communication_level() == "verbose"

    def test_normal(self):
        p = Persona(name="N", age=30, sex="male", occupation="x", extraversion=5)
        assert PersonalityMechanics(p).communication_level() == "normal"


class TestPrioritizeOthersPlans:
    def test_cautious(self, cautious_persona):
        # agreeableness=7 -> True
        assert PersonalityMechanics(cautious_persona).prioritize_others_plans() is True

    def test_bold(self, bold_persona):
        # agreeableness=4 -> False
        assert PersonalityMechanics(bold_persona).prioritize_others_plans() is False

    def test_boundary_six(self):
        p = Persona(name="B", age=30, sex="male", occupation="x", agreeableness=6)
        assert PersonalityMechanics(p).prioritize_others_plans() is True


class TestActInstructionsText:
    def test_returns_string(self, bold_persona):
        text = PersonalityMechanics(bold_persona).act_instructions_text()
        assert isinstance(text, str)
        assert len(text) > 0


# ── REFLECT phase ────────────────────────────────────────────────────────


class TestReplanThreshold:
    def test_cautious(self, cautious_persona):
        # neuroticism=8 -> >=7 -> 1
        assert PersonalityMechanics(cautious_persona).replan_threshold() == 1

    def test_bold(self, bold_persona):
        # neuroticism=2 -> <4 -> 3
        assert PersonalityMechanics(bold_persona).replan_threshold() == 3

    def test_mid_neuroticism(self):
        p = Persona(name="M", age=30, sex="male", occupation="x", neuroticism=5)
        assert PersonalityMechanics(p).replan_threshold() == 2

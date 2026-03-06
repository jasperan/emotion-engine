"""Translates Big Five personality traits into mechanical constraints for cognitive phases."""
from __future__ import annotations

from app.schemas.persona import Persona


class PersonalityMechanics:
    """Maps a Persona's traits to concrete constraints for THINK, PLAN, ACT, REFLECT phases."""

    def __init__(self, persona: Persona) -> None:
        self.persona = persona

    # ── THINK phase ──────────────────────────────────────────────────────

    def urgency_modifier(self) -> int:
        """Neuroticism amplifies urgency. Returns -2 to +2."""
        return round((self.persona.neuroticism - 5) * 0.5)

    def include_novel_options(self) -> bool:
        """High openness (>=6) enables consideration of creative/novel options."""
        return self.persona.openness >= 6

    def think_prompt_additions(self) -> str:
        """Return personality-specific prompt text for the THINK phase."""
        parts: list[str] = []

        urgency = self.urgency_modifier()
        if urgency >= 1:
            parts.append(
                "You feel a heightened sense of urgency; threats feel amplified."
            )
        elif urgency <= -1:
            parts.append(
                "You feel calm under pressure; threats seem manageable."
            )

        if self.include_novel_options():
            parts.append(
                "Consider creative or unconventional options alongside standard ones."
            )
        else:
            parts.append(
                "Stick to practical, proven approaches rather than untested ideas."
            )

        if self.persona.empathy_level >= 7:
            parts.append("You are acutely aware of others' distress and needs.")
        elif self.persona.empathy_level <= 3:
            parts.append("Focus on your own survival first.")

        return " ".join(parts)

    # ── PLAN phase ───────────────────────────────────────────────────────

    def max_plan_steps(self) -> int:
        """Conscientiousness determines plan length (1-5)."""
        c = self.persona.conscientiousness
        if c >= 8:
            return 5
        if c >= 6:
            return 3
        if c >= 4:
            return 2
        return 1

    def deadline_patience(self) -> int:
        """Ticks before fallback action. Minimum 2."""
        base = 5
        neuro_mod = -(self.persona.neuroticism - 5)
        consc_mod = (self.persona.conscientiousness - 5) * 0.5
        return max(2, int(base + neuro_mod + consc_mod))

    def allowed_risk_level(self) -> str:
        """Risk tolerance mapped to categorical level."""
        rt = self.persona.risk_tolerance
        if rt >= 7:
            return "high"
        if rt >= 4:
            return "medium"
        return "low"

    def coordination_style(self) -> str:
        """Leadership trait mapped to coordination style."""
        ld = self.persona.leadership
        if ld >= 7:
            return "leader"
        if ld >= 4:
            return "collaborator"
        return "solo"

    def plan_constraints_text(self) -> str:
        """Return personality-specific plan constraints."""
        parts: list[str] = []

        steps = self.max_plan_steps()
        parts.append(f"Limit your plan to at most {steps} steps.")

        risk = self.allowed_risk_level()
        if risk == "low":
            parts.append("Avoid risky actions; prefer safe, incremental progress.")
        elif risk == "high":
            parts.append("Bold moves are acceptable when the payoff justifies the risk.")
        else:
            parts.append("Balance caution with opportunity.")

        style = self.coordination_style()
        if style == "leader":
            parts.append("Take charge and delegate tasks to others.")
        elif style == "collaborator":
            parts.append("Look for ways to cooperate and share responsibility.")
        else:
            parts.append("Prefer to work independently unless cooperation is essential.")

        patience = self.deadline_patience()
        parts.append(
            f"If no progress after {patience} ticks, switch to a fallback plan."
        )

        return " ".join(parts)

    # ── ACT phase ────────────────────────────────────────────────────────

    def communication_level(self) -> str:
        """Extraversion mapped to communication verbosity."""
        e = self.persona.extraversion
        if e >= 7:
            return "verbose"
        if e >= 4:
            return "normal"
        return "minimal"

    def prioritize_others_plans(self) -> bool:
        """High agreeableness (>=6) defers to others' plans."""
        return self.persona.agreeableness >= 6

    def act_instructions_text(self) -> str:
        """Return personality-specific act instructions."""
        parts: list[str] = []

        comm = self.communication_level()
        if comm == "verbose":
            parts.append(
                "Communicate openly; share observations and intentions with others."
            )
        elif comm == "minimal":
            parts.append("Keep communication brief; act more than you speak.")
        else:
            parts.append("Communicate as needed to coordinate actions.")

        if self.prioritize_others_plans():
            parts.append(
                "If others have a reasonable plan, support it rather than imposing your own."
            )
        else:
            parts.append("Pursue your own plan unless a clearly better option emerges.")

        return " ".join(parts)

    # ── REFLECT phase ────────────────────────────────────────────────────

    def replan_threshold(self) -> int:
        """Failures before replanning. High neuroticism replans sooner."""
        n = self.persona.neuroticism
        if n >= 7:
            return 1
        if n >= 4:
            return 2
        return 3

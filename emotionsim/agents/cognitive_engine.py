"""Cognitive engine: orchestrates the think -> plan -> act -> reflect cycle."""
from __future__ import annotations

import json
from enum import Enum
from typing import Any, Callable, Awaitable

from emotionsim.agents.intent_memory import IntentMemory, Plan
from emotionsim.agents.personality_mechanics import PersonalityMechanics
from emotionsim.schemas.persona import Persona
from emotionsim.llm.base import LLMMessage, LLMResponse
from emotionsim.llm.schemas import PlanResponse, ThinkResponse, validate_content


class CognitivePhase(Enum):
    THINK = "think"
    PLAN = "plan"
    ACT = "act"


# Type alias for the LLM generate callable
LLMGenerateFn = Callable[..., Awaitable[LLMResponse]]

_URGENCY_LEVELS = ["low", "medium", "high"]


class CognitiveEngine:
    """Orchestrates the think -> plan -> act -> reflect cognitive cycle for agents."""

    def __init__(self, persona: Persona) -> None:
        self.persona = persona
        self.mechanics = PersonalityMechanics(persona)

    # ── Phase determination ───────────────────────────────────────────

    def determine_phases(
        self, intent: IntentMemory, current_step: int
    ) -> list[CognitivePhase]:
        """Decide which cognitive phases to run this tick.

        Returns [THINK, PLAN, ACT] if replanning is needed, [ACT] otherwise.
        Step 0 always skips THINK+PLAN (react instinctively first, plan later).
        """
        if current_step == 0:
            return [CognitivePhase.ACT]

        needs_full = (
            intent.current_plan is None
            or intent.plan_needs_replan(current_step)
            or intent.plan_deadline_exceeded(current_step)
        )
        if needs_full:
            return [CognitivePhase.THINK, CognitivePhase.PLAN, CognitivePhase.ACT]
        return [CognitivePhase.ACT]

    # ── THINK phase ───────────────────────────────────────────────────

    async def think(
        self,
        world_state: str,
        memory_context: str,
        recent_messages: list[str],
        llm_generate: LLMGenerateFn,
    ) -> dict[str, Any]:
        """Assess the situation and determine urgency/needs.

        Returns {"urgency": "high|medium|low", "assessment": "...", "top_need": "..."}.
        """
        personality_text = self.mechanics.think_prompt_additions()

        system_prompt = (
            f"You are analyzing a situation as {self.persona.name}. "
            f"{personality_text} "
            "Respond with JSON containing: urgency (high/medium/low), "
            "assessment (1-2 sentence situation analysis), "
            "top_need (single most important need right now)."
        )

        messages_text = "\n".join(recent_messages) if recent_messages else "No recent messages."
        user_prompt = (
            f"World state: {world_state}\n\n"
            f"Your memories: {memory_context}\n\n"
            f"Recent messages:\n{messages_text}\n\n"
            "Analyze the situation and respond with JSON."
        )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        response = await llm_generate(
            messages=messages,
            json_mode=True,
            temperature=0.7,
            max_tokens=512,
        )

        # Structured-output enforcement: validate against the schema and
        # retry once with the validation error injected into the prompt.
        ok, _, err = validate_content(response.content, ThinkResponse)
        if not ok:
            response = await llm_generate(
                messages=messages
                + [
                    LLMMessage(
                        role="user",
                        content=(
                            f"Your previous response failed validation: {err}\n"
                            "Return ONLY valid JSON with fields: "
                            "urgency (high/medium/low), assessment (string), "
                            "top_need (string)."
                        ),
                    )
                ],
                json_mode=True,
                temperature=0.7,
                max_tokens=512,
            )

        result = self._parse_think_response(response.content)

        # Apply urgency modifier from personality
        result["urgency"] = self._apply_urgency_modifier(result["urgency"])

        return result

    def _parse_think_response(self, content: str) -> dict[str, Any]:
        """Parse LLM JSON response, falling back to defaults."""
        try:
            data = json.loads(content)
            return {
                "urgency": data.get("urgency", "medium"),
                "assessment": data.get("assessment", "Situation unclear."),
                "top_need": data.get("top_need", "survival"),
            }
        except (json.JSONDecodeError, TypeError):
            return {
                "urgency": "medium",
                "assessment": content[:200] if content else "Unable to assess.",
                "top_need": "survival",
            }

    def _apply_urgency_modifier(self, urgency: str) -> str:
        """Shift urgency level by personality modifier."""
        modifier = self.mechanics.urgency_modifier()
        if modifier == 0:
            return urgency

        try:
            idx = _URGENCY_LEVELS.index(urgency)
        except ValueError:
            return urgency

        new_idx = max(0, min(len(_URGENCY_LEVELS) - 1, idx + modifier))
        return _URGENCY_LEVELS[new_idx]

    # ── PLAN phase ────────────────────────────────────────────────────

    async def plan(
        self,
        assessment: dict[str, Any],
        intent: IntentMemory,
        world_state: str,
        llm_generate: LLMGenerateFn,
        current_step: int,
    ) -> Plan:
        """Generate an action plan based on assessment.

        Returns a Plan dataclass.
        """
        constraints = self.mechanics.plan_constraints_text()

        # Build blocked actions text
        blocked_text = ""
        if intent.blocked_actions:
            blocked_lines = [
                f"- {ba.action}: {ba.reason}" for ba in intent.blocked_actions
            ]
            blocked_text = (
                "\n\nPreviously failed actions (DO NOT repeat):\n"
                + "\n".join(blocked_lines)
            )

        system_prompt = (
            f"You are {self.persona.name} creating an action plan. "
            f"{constraints} "
            "CRITICAL: Every step must be a physical action, not discuss/wait. "
            "Respond with JSON containing: goal (string), steps (list of action strings), "
            "success_criteria (string), fallback (string or null)."
        )

        user_prompt = (
            f"Situation assessment: {assessment.get('assessment', 'Unknown')}\n"
            f"Urgency: {assessment.get('urgency', 'medium')}\n"
            f"Top need: {assessment.get('top_need', 'survival')}\n"
            f"World state: {world_state}"
            f"{blocked_text}\n\n"
            "Create a concrete action plan."
        )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        response = await llm_generate(
            messages=messages,
            json_mode=True,
            temperature=0.7,
            max_tokens=1024,
        )

        # Structured-output enforcement: validate against the schema and
        # retry once with the validation error injected into the prompt.
        ok, _, err = validate_content(response.content, PlanResponse)
        if not ok:
            response = await llm_generate(
                messages=messages
                + [
                    LLMMessage(
                        role="user",
                        content=(
                            f"Your previous response failed validation: {err}\n"
                            "Return ONLY valid JSON with fields: "
                            "goal (string), steps (list of action strings), "
                            "success_criteria (string), fallback (string or null)."
                        ),
                    )
                ],
                json_mode=True,
                temperature=0.7,
                max_tokens=1024,
            )

        return self._parse_plan_response(response.content, current_step)

    def _parse_plan_response(self, content: str, current_step: int) -> Plan:
        """Parse LLM plan response into Plan dataclass."""
        max_steps = self.mechanics.max_plan_steps()
        patience = self.mechanics.deadline_patience()

        try:
            data = json.loads(content)
            steps = data.get("steps", ["Take immediate protective action"])
            # Cap steps at personality limit
            steps = steps[:max_steps]

            return Plan(
                goal=data.get("goal", "Survive"),
                steps=steps,
                current_step=0,
                created_at_step=current_step,
                success_criteria=data.get("success_criteria", "Situation improved"),
                fallback=data.get("fallback"),
                deadline_step=current_step + patience,
                retry_count=0,
            )
        except (json.JSONDecodeError, TypeError):
            # Fallback plan
            return Plan(
                goal="Survive and adapt",
                steps=["Take immediate protective action"],
                current_step=0,
                created_at_step=current_step,
                success_criteria="Situation improved",
                fallback=None,
                deadline_step=current_step + patience,
                retry_count=0,
            )

    # ── REFLECT phase (code-only, no LLM) ────────────────────────────

    def reflect(
        self,
        intent: IntentMemory,
        actions_taken: list[str],
        current_step: int,
    ) -> None:
        """Evaluate progress and update plan state. No LLM call."""
        if intent.current_plan is None:
            return

        trivial_actions = {"wait", "speak"}
        has_nontrivial = any(
            action not in trivial_actions for action in actions_taken
        )

        if has_nontrivial:
            intent.advance_plan_step()
            intent.current_plan.retry_count = 0
            # Check if plan is now complete
            if intent.current_plan.current_step >= len(intent.current_plan.steps):
                intent.complete_plan("success", "All plan steps completed")
        else:
            intent.current_plan.retry_count += 1
            threshold = self.mechanics.replan_threshold()
            if intent.current_plan.retry_count >= threshold:
                intent.complete_plan("failed", "Too many retries without progress")

"""Lightweight rule-based agent for 100+ agent scaling.

Not every agent needs the full CognitiveEngine (THINK -> PLAN -> ACT -> REFLECT)
with LLM calls every tick. LightweightAgent uses personality-driven probabilities
to make decisions without any LLM calls, running orders of magnitude faster than
HumanAgent.
"""

import random
from dataclasses import dataclass, field
from typing import Any

from app.schemas.persona import Persona


@dataclass
class LightweightDecision:
    """Result of a lightweight agent's tick."""

    action_type: str  # "speak", "move", "help", "wait", "gather", "observe"
    message: str | None = None  # if action_type == "speak"
    target_location: str | None = None  # if action_type == "move"
    target_agent: str | None = None  # if action_type == "help"
    reasoning: str = ""


class LightweightAgent:
    """Rule-based agent for background simulation. No LLM calls.

    Behavior is driven by Big Five personality traits:
    - High extraversion -> more likely to speak
    - High agreeableness -> more likely to help
    - High openness -> more likely to explore/move
    - High conscientiousness -> more likely to gather resources
    - High neuroticism -> more likely to wait/observe when stressed
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        persona: Persona,
        location: str = "unknown",
    ):
        self.agent_id = agent_id
        self.name = name
        self.persona = persona
        self.location = location
        self.is_foreground = False  # can be promoted to full HumanAgent
        self._action_history: list[str] = []

    def tick(
        self,
        world_state: dict[str, Any],
        nearby_agents: list[str],
        recent_messages: list[dict[str, Any]],
        step: int,
    ) -> LightweightDecision:
        """Make a decision based on personality probabilities. No LLM call."""
        weights = self._compute_action_weights(nearby_agents, recent_messages)

        actions = list(weights.keys())
        probs = list(weights.values())
        total = sum(probs)
        probs = [p / total for p in probs]

        chosen = random.choices(actions, weights=probs, k=1)[0]
        decision = self._build_decision(
            chosen, world_state, nearby_agents, recent_messages, step
        )
        self._action_history.append(decision.action_type)
        return decision

    def _compute_action_weights(
        self,
        nearby_agents: list[str],
        recent_messages: list[dict[str, Any]],
    ) -> dict[str, float]:
        """Compute probability weights for each action type based on personality."""
        p = self.persona
        stress = getattr(p, "stress_level", 5)

        weights = {
            "speak": max(0.1, p.extraversion / 10.0),
            "help": max(0.1, p.agreeableness / 10.0 * p.empathy_level / 10.0),
            "move": max(0.1, p.openness / 10.0 * p.risk_tolerance / 10.0),
            "gather": max(0.1, p.conscientiousness / 10.0),
            "observe": max(0.1, p.neuroticism / 10.0 * stress / 10.0),
            "wait": max(0.1, (10 - p.extraversion) / 10.0),
        }

        # Boost speak if there are recent messages to respond to
        if recent_messages:
            weights["speak"] *= 1.5

        # Boost help if there are nearby agents
        if nearby_agents:
            weights["help"] *= 1.3
        else:
            weights["help"] *= 0.3  # can't help if nobody's around

        return weights

    def _build_decision(
        self,
        action_type: str,
        world_state: dict[str, Any],
        nearby_agents: list[str],
        recent_messages: list[dict[str, Any]],
        step: int,
    ) -> LightweightDecision:
        """Build a decision with appropriate details based on action type."""
        if action_type == "speak":
            templates = self._get_speech_templates()
            message = random.choice(templates)
            return LightweightDecision(
                action_type="speak",
                message=message,
                reasoning=(
                    f"Personality-driven ({self.name}: "
                    f"extraversion={self.persona.extraversion})"
                ),
            )
        elif action_type == "move":
            locations = list(world_state.get("locations", {}).keys())
            other_locations = [loc for loc in locations if loc != self.location]
            target = random.choice(other_locations) if other_locations else None
            return LightweightDecision(
                action_type="move",
                target_location=target,
                reasoning=f"Exploring (openness={self.persona.openness})",
            )
        elif action_type == "help":
            target = random.choice(nearby_agents) if nearby_agents else None
            return LightweightDecision(
                action_type="help",
                target_agent=target,
                reasoning=f"Helping (agreeableness={self.persona.agreeableness})",
            )
        elif action_type == "gather":
            return LightweightDecision(
                action_type="gather",
                reasoning=(
                    f"Gathering resources "
                    f"(conscientiousness={self.persona.conscientiousness})"
                ),
            )
        elif action_type == "observe":
            return LightweightDecision(
                action_type="observe",
                reasoning=f"Observing cautiously (neuroticism={self.persona.neuroticism})",
            )
        else:
            return LightweightDecision(action_type="wait", reasoning="Waiting")

    def _get_speech_templates(self) -> list[str]:
        """Simple speech templates based on personality."""
        templates = [
            "Is everyone okay?",
            "We should stick together.",
            "What's the plan?",
        ]
        if self.persona.leadership >= 7:
            templates.extend([
                "Follow me, I know what to do.",
                "Let's organize and help each other.",
            ])
        if self.persona.neuroticism >= 7:
            templates.extend([
                "I'm worried about what's coming.",
                "This doesn't look good...",
            ])
        if self.persona.agreeableness >= 7:
            templates.extend([
                "How can I help?",
                "Does anyone need anything?",
            ])
        if self.persona.extraversion <= 3:
            templates = ["...", "*nods quietly*", "Hmm."]
        return templates

    def should_promote(
        self,
        addressed_directly: bool = False,
        in_active_scene: bool = False,
    ) -> bool:
        """Check if this background agent should be promoted to foreground.

        Triggers:
        - Addressed directly by another agent
        - In an active scene with high extraversion
        - High leadership + low stress (natural leaders step up)
        """
        if addressed_directly:
            return True
        if in_active_scene and self.persona.extraversion >= 7:
            return True
        if self.persona.leadership >= 8 and getattr(self.persona, "stress_level", 5) <= 4:
            return True
        return False

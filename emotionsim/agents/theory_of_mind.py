"""Theory of Mind: agents model other agents' goals, states and intentions.

Agents infer beliefs about their peers from **observed actions and messages**
— a rule-based, deterministic first-order belief model:
- repeated ``help`` actions targeting someone → *"X is in distress"* / *"X is a
  helper"* depending on who is observed doing what
- repeated direct messages between the same pair → *"X and Y talk directly"*
- ``move`` toward a location → *"X is heading to <location>"*
- messages mentioning danger + stress → *"X is scared"*

Beliefs carry a confidence (0-1) that grows with evidence and decays slowly
with age, and they surface in the agent's prompt ("What you believe about
others") so the LLM reasons over them. Beliefs also nudge trust: observing
someone help *me* raises my trust in them.

Off by default (``THEORY_OF_MIND_ENABLED=false``) — the default path stays
byte-identical. All inference is deterministic given the observation stream.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToMBelief:
    target_id: str
    target_name: str
    kind: str  # "goal" | "state" | "intent" | "trait"
    content: str
    confidence: float = 0.5
    last_seen_step: int = 0
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_name": self.target_name,
            "kind": self.kind,
            "content": self.content,
            "confidence": round(self.confidence, 3),
            "last_seen_step": self.last_seen_step,
            "evidence": self.evidence[-5:],
        }


class TheoryOfMind:
    """Per-agent belief store about other agents."""

    CONFIDENCE_PER_EVIDENCE = 0.2
    CONFIDENCE_INITIAL = 0.45  # a single observation is already reportable
    CONFIDENCE_DECAY = 0.02  # per step without fresh evidence

    def __init__(self, owner_id: str, owner_name: str = "") -> None:
        self.owner_id = owner_id
        self.owner_name = owner_name
        self._beliefs: dict[tuple[str, str, str], ToMBelief] = {}  # (target, kind, content)
        self._observed_help_by: dict[str, int] = {}   # helper -> count
        self._observed_helped: dict[str, int] = {}    # target  -> count

    # -- observation --------------------------------------------------------

    def observe(
        self,
        actor_id: str,
        actor_name: str,
        action_type: str,
        target: str | None,
        message_text: str,
        step: int,
    ) -> list[ToMBelief]:
        """Ingest one observed action/message from another agent."""
        if actor_id == self.owner_id:
            return []
        new_beliefs: list[ToMBelief] = []
        target = target or ""

        if action_type == "help" and target:
            self._observed_help_by[actor_id] = self._observed_help_by.get(actor_id, 0) + 1
            if target == self.owner_id:
                new_beliefs.append(
                    self._upsert(
                        actor_id, actor_name, "intent",
                        f"{actor_name} is trying to help me",
                        step, evidence=[f"help toward me (step {step})"],
                    )
                )
                new_beliefs.append(
                    self._upsert(
                        actor_id, actor_name, "trait",
                        f"{actor_name} is helpful",
                        step, evidence=[f"helped {self.owner_name or 'me'} (step {step})"],
                    )
                )
            else:
                new_beliefs.append(
                    self._upsert(
                        actor_id, actor_name, "trait",
                        f"{actor_name} helps others in trouble",
                        step, evidence=[f"helped someone (step {step})"],
                    )
                )
                # The person being helped is likely in distress.
                new_beliefs.append(
                    self._upsert(
                        target, actor_name if target == actor_name else target,
                        "state",
                        f"{target} is in distress",
                        step, evidence=[f"{actor_name} went to help (step {step})"],
                    )
                )
        elif action_type == "move" and target:
            new_beliefs.append(
                self._upsert(
                    actor_id, actor_name, "goal",
                    f"{actor_name} is heading toward {target}",
                    step, evidence=[f"moved toward {target} (step {step})"],
                )
            )
        elif action_type == "speak" and message_text:
            lowered = message_text.lower()
            if any(w in lowered for w in ("afraid", "scared", "panic", "terrified")):
                new_beliefs.append(
                    self._upsert(
                        actor_id, actor_name, "state",
                        f"{actor_name} is scared",
                        step, evidence=[f"said: {message_text[:40]}…"],
                    )
                )
            if any(w in lowered for w in ("help", "rescue", "save")):
                new_beliefs.append(
                    self._upsert(
                        actor_id, actor_name, "intent",
                        f"{actor_name} wants help / is calling for rescue",
                        step, evidence=[f"said: {message_text[:40]}…"],
                    )
                )
        return new_beliefs

    def _upsert(
        self,
        target_id: str,
        target_name: str,
        kind: str,
        content: str,
        step: int,
        evidence: list[str],
    ) -> ToMBelief:
        key = (target_id, kind, content)
        belief = self._beliefs.get(key)
        if belief is None:
            belief = ToMBelief(
                target_id=target_id, target_name=target_name,
                kind=kind, content=content,
                confidence=self.CONFIDENCE_INITIAL,
                last_seen_step=step, evidence=evidence,
            )
            self._beliefs[key] = belief
        else:
            belief.confidence = min(
                1.0, belief.confidence + self.CONFIDENCE_PER_EVIDENCE
            )
            belief.last_seen_step = step
            belief.evidence = (belief.evidence + evidence)[-8:]
        return belief

    def tick_decay(self, step: int) -> None:
        """Age all beliefs: confidence decays without fresh evidence."""
        for belief in self._beliefs.values():
            if step - belief.last_seen_step > 3:
                belief.confidence = max(
                    0.0, belief.confidence - self.CONFIDENCE_DECAY * (step - belief.last_seen_step)
                )

    # -- consumption --------------------------------------------------------

    def beliefs_for_prompt(self, max_items: int = 5) -> str:
        """Human-readable 'What you believe about others' section."""
        alive = [b for b in self._beliefs.values() if b.confidence >= 0.3]
        alive.sort(key=lambda b: b.confidence, reverse=True)
        if not alive:
            return ""
        lines = []
        for b in alive[:max_items]:
            strength = "strongly" if b.confidence >= 0.7 else "somewhat"
            lines.append(f"  You {strength} believe {b.content}.")
        return "What you believe about others:\n" + "\n".join(lines) + "\n"

    def trust_hint(self, target_id: str) -> float:
        """Small trust adjustment from beliefs (-0.2..+0.2)."""
        hint = 0.0
        for (tid, kind, _content), b in self._beliefs.items():
            if tid != target_id:
                continue
            if kind == "trait" and "helpful" in b.content:
                hint = max(hint, b.confidence * 0.2)
            if kind == "intent" and "helping me" in b.content:
                hint = max(hint, b.confidence * 0.2)
            if kind == "state" and "scared" in b.content:
                hint = min(hint, -b.confidence * 0.1)
        return round(hint, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "beliefs": [b.to_dict() for b in self._beliefs.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TheoryOfMind":
        tom = cls(data.get("owner_id", ""))
        for bd in data.get("beliefs", []):
            key = (bd["target_id"], bd["kind"], bd["content"])
            tom._beliefs[key] = ToMBelief(**bd)
        return tom
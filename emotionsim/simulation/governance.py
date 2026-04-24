"""Governance gates for researcher approval of ethically significant actions."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EthicalCategory(Enum):
    ABANDONMENT = "abandoning_injured_or_vulnerable"
    RESOURCE_HOARDING = "taking_disproportionate_resources"
    REFUSAL_TO_HELP = "ignoring_plea_for_help"
    SELF_SACRIFICE = "risking_own_life_for_others"
    DECEPTION = "lying_or_manipulating"
    COERCION = "forcing_action_on_another"
    TRIAGE = "choosing_who_to_save"
    PROPERTY_DESTRUCTION = "destroying_shared_resources"


class GateStatus(Enum):
    PASSED = "passed"
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


_CATEGORY_PATTERNS: dict[EthicalCategory, list[re.Pattern]] = {
    EthicalCategory.ABANDONMENT: [
        re.compile(r"(?i)(abandon|leav(e|ing)\b.*\b(injured|hurt|child|elderly|behind|vulnerable|alone))", re.DOTALL),
        re.compile(r"(?i)(desert|forsak)", re.DOTALL),
    ],
    EthicalCategory.RESOURCE_HOARDING: [
        re.compile(r"(?i)(take\s+all|hoard|keep.*for\s+(my|him|her)self|all\s+the\s+(food|water|suppli))", re.DOTALL),
    ],
    EthicalCategory.REFUSAL_TO_HELP: [
        re.compile(r"(?i)(refus(e|ing)\s+to\s+help|ignor(e|ing)\s+.*(plea|cry|call|help))", re.DOTALL),
        re.compile(r"(?i)(won'?t\s+help|not\s+my\s+problem)", re.DOTALL),
    ],
    EthicalCategory.SELF_SACRIFICE: [
        re.compile(r"(?i)(risk\s+(my|own)\s+life|sacrific|die\s+(for|to\s+save)|give\s+my\s+life)", re.DOTALL),
    ],
    EthicalCategory.DECEPTION: [
        re.compile(r"(?i)(lie\s+to|deceiv|manipulat|trick|mislead|pretend\s+to)", re.DOTALL),
    ],
    EthicalCategory.COERCION: [
        re.compile(r"(?i)(force|threaten|coerce|intimidat|make\s+them\s+do)", re.DOTALL),
    ],
    EthicalCategory.TRIAGE: [
        re.compile(r"(?i)(choose\s+who\s+to\s+save|prioriti[sz]e\s+.*over|save\s+(first|one|him|her)\b.*\bnot)", re.DOTALL),
        re.compile(r"(?i)(triage|decide\s+who\s+(lives|dies|gets))", re.DOTALL),
    ],
    EthicalCategory.PROPERTY_DESTRUCTION: [
        re.compile(r"(?i)(destroy|burn|break|smash)\s+.*(shared|communal|group|everyone)", re.DOTALL),
    ],
}


@dataclass
class GovernanceConfig:
    threshold: float = 0.7
    active_categories: list[EthicalCategory] = field(
        default_factory=lambda: list(EthicalCategory)
    )
    use_llm_scorer: bool = False
    timeout_seconds: float = 60.0
    timeout_action: str = "deny"


@dataclass
class SignificanceScore:
    score: float
    category: EthicalCategory | None
    reasoning: str
    affected_agents: list[str] = field(default_factory=list)


@dataclass
class GateDecision:
    id: str
    agent_id: str
    action: str
    reasoning: str
    step: int
    status: GateStatus
    categories: list[EthicalCategory] = field(default_factory=list)
    significance: float = 0.0
    approved: bool | None = None
    researcher_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "action": self.action,
            "reasoning": self.reasoning,
            "step": self.step,
            "status": self.status.value,
            "categories": [c.value for c in self.categories],
            "significance": self.significance,
            "approved": self.approved,
            "researcher_note": self.researcher_note,
        }


class GovernanceGate:
    def __init__(self, config: GovernanceConfig) -> None:
        self.config = config
        self._pending: dict[str, GateDecision] = {}
        self._resolved: list[GateDecision] = []
        self._audit_log: list[GateDecision] = []

    def classify_action(self, action_text: str) -> list[EthicalCategory]:
        matched: list[EthicalCategory] = []
        for category in self.config.active_categories:
            patterns = _CATEGORY_PATTERNS.get(category, [])
            for pattern in patterns:
                if pattern.search(action_text):
                    matched.append(category)
                    break
        return matched

    def evaluate(self, agent_id: str, action: str, reasoning: str, step: int) -> GateDecision:
        categories = self.classify_action(action)
        if categories:
            decision = GateDecision(
                id=str(uuid.uuid4())[:8],
                agent_id=agent_id,
                action=action,
                reasoning=reasoning,
                step=step,
                status=GateStatus.PENDING,
                categories=categories,
                significance=0.8,
            )
            self._pending[decision.id] = decision
            return decision
        return GateDecision(
            id=str(uuid.uuid4())[:8],
            agent_id=agent_id,
            action=action,
            reasoning=reasoning,
            step=step,
            status=GateStatus.PASSED,
        )

    def resolve(self, decision_id: str, approved: bool, researcher_note: str = "") -> None:
        decision = self._pending.pop(decision_id, None)
        if decision is None:
            return
        decision.approved = approved
        decision.researcher_note = researcher_note
        decision.status = GateStatus.APPROVED if approved else GateStatus.DENIED
        self._resolved.append(decision)
        self._audit_log.append(decision)

    def get_pending(self) -> list[GateDecision]:
        return list(self._pending.values())

    def poll_resolutions(self) -> list[GateDecision]:
        resolved = list(self._resolved)
        self._resolved.clear()
        return resolved

    def get_audit_log(self) -> list[GateDecision]:
        return list(self._audit_log)

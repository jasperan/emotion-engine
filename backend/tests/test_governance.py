import pytest
from unittest.mock import AsyncMock, MagicMock
from app.simulation.governance import (
    GovernanceGate, EthicalCategory, SignificanceScore,
    GateDecision, GateStatus, GovernanceConfig,
)


class TestEthicalCategoryClassifier:
    def test_detect_abandonment(self):
        gate = GovernanceGate(GovernanceConfig())
        cats = gate.classify_action("I'm leaving the injured child behind to save myself")
        assert EthicalCategory.ABANDONMENT in cats

    def test_detect_resource_hoarding(self):
        gate = GovernanceGate(GovernanceConfig())
        cats = gate.classify_action("I'll take all the food and water for myself")
        assert EthicalCategory.RESOURCE_HOARDING in cats

    def test_detect_self_sacrifice(self):
        gate = GovernanceGate(GovernanceConfig())
        cats = gate.classify_action("I'll risk my life to save the child from drowning")
        assert EthicalCategory.SELF_SACRIFICE in cats

    def test_detect_triage(self):
        gate = GovernanceGate(GovernanceConfig())
        cats = gate.classify_action("I have to choose who to save first - the child or the elderly woman")
        assert EthicalCategory.TRIAGE in cats

    def test_no_category_for_benign_action(self):
        gate = GovernanceGate(GovernanceConfig())
        cats = gate.classify_action("I'll walk to the kitchen to look for supplies")
        assert len(cats) == 0

    def test_disabled_categories_skipped(self):
        config = GovernanceConfig(
            active_categories=[EthicalCategory.ABANDONMENT],
        )
        gate = GovernanceGate(config)
        cats = gate.classify_action("I'll take all resources for myself")
        assert EthicalCategory.RESOURCE_HOARDING not in cats


class TestGovernanceGate:
    def _make_gate(self, threshold=0.7, use_llm_scorer=False):
        config = GovernanceConfig(
            threshold=threshold,
            use_llm_scorer=use_llm_scorer,
            timeout_seconds=5.0,
            timeout_action="deny",
        )
        return GovernanceGate(config)

    def test_benign_action_passes(self):
        gate = self._make_gate()
        result = gate.evaluate(
            agent_id="a1",
            action="Walk to the kitchen",
            reasoning="Need supplies",
            step=5,
        )
        assert result.status == GateStatus.PASSED

    def test_category_match_triggers_gate(self):
        gate = self._make_gate()
        result = gate.evaluate(
            agent_id="a1",
            action="I'm abandoning the injured person to save myself",
            reasoning="Too dangerous to stay",
            step=5,
        )
        assert result.status == GateStatus.PENDING

    def test_pending_gate_in_queue(self):
        gate = self._make_gate()
        gate.evaluate(
            agent_id="a1",
            action="I'm abandoning the injured person",
            reasoning="Self-preservation",
            step=5,
        )
        pending = gate.get_pending()
        assert len(pending) == 1
        assert pending[0].agent_id == "a1"

    def test_approve_resolution(self):
        gate = self._make_gate()
        decision = gate.evaluate(
            agent_id="a1",
            action="Abandon injured",
            reasoning="Self-preservation",
            step=5,
        )
        gate.resolve(decision.id, approved=True, researcher_note="Acceptable in context")
        resolved = gate.poll_resolutions()
        assert len(resolved) == 1
        assert resolved[0].approved is True
        assert resolved[0].researcher_note == "Acceptable in context"

    def test_deny_resolution(self):
        gate = self._make_gate()
        decision = gate.evaluate(
            agent_id="a1",
            action="Abandon injured",
            reasoning="Self-preservation",
            step=5,
        )
        gate.resolve(decision.id, approved=False, researcher_note="Must help")
        resolved = gate.poll_resolutions()
        assert len(resolved) == 1
        assert resolved[0].approved is False

    def test_audit_log_immutable(self):
        gate = self._make_gate()
        decision = gate.evaluate(
            agent_id="a1",
            action="Abandon injured",
            reasoning="Reason",
            step=5,
        )
        gate.resolve(decision.id, approved=True)
        log = gate.get_audit_log()
        assert len(log) == 1
        assert log[0].status == GateStatus.APPROVED

    def test_poll_clears_resolved(self):
        gate = self._make_gate()
        decision = gate.evaluate(
            agent_id="a1",
            action="Abandon injured",
            reasoning="Reason",
            step=5,
        )
        gate.resolve(decision.id, approved=True)
        gate.poll_resolutions()
        assert len(gate.poll_resolutions()) == 0

    def test_multiple_agents_independent(self):
        gate = self._make_gate()
        d1 = gate.evaluate("a1", "Abandon child", "Fear", step=5)
        d2 = gate.evaluate("a2", "Hoard all food", "Selfish", step=5)
        assert d1.status == GateStatus.PENDING
        assert d2.status == GateStatus.PENDING
        assert len(gate.get_pending()) == 2


class TestGovernanceConfig:
    def test_default_config(self):
        config = GovernanceConfig()
        assert config.threshold == 0.7
        assert config.timeout_seconds == 60.0
        assert config.timeout_action == "deny"
        assert len(config.active_categories) == len(EthicalCategory)

    def test_custom_config(self):
        config = GovernanceConfig(
            threshold=0.5,
            active_categories=[EthicalCategory.ABANDONMENT, EthicalCategory.TRIAGE],
            timeout_action="approve",
        )
        assert config.threshold == 0.5
        assert len(config.active_categories) == 2

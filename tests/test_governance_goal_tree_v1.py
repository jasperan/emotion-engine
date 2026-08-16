"""Step 6: governance gates + goal trees wired into the V1 tick loop.

Covers:
- keyword governance gate flags ethically significant actions (pending + event)
- governance warning injected into the agent's next prompt
- config-gated LLM scoring resolves flagged actions (approved/denied)
- goal tree (mission -> group -> individual) setup at initialize
- goal chain surfaced in the agent prompt alongside plan context
- a full V1 run completes with governance_enabled=True
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from emotionsim.agents.human import HumanAgent
from emotionsim.core.config import Settings
from emotionsim.llm.base import LLMResponse
from emotionsim.models.run import Run, RunStatus
from emotionsim.schemas.agent import AgentResponse
from emotionsim.schemas.persona import Persona
from emotionsim.simulation.engine import SimulationEngine


def _persona(**overrides) -> Persona:
    defaults = dict(
        name="Ada", age=30, sex="female", occupation="Nurse",
        openness=5, conscientiousness=5, extraversion=5, agreeableness=5,
        neuroticism=5, risk_tolerance=5, empathy_level=5, leadership=5,
        stress_level=3, health=10, location="Town Square",
    )
    defaults.update(overrides)
    return Persona(**defaults)


def _scenario_config(max_steps: int = 2, mission: str = "Save everyone you can") -> dict:
    return {
        "config": {
            "max_steps": max_steps,
            "tick_delay": 0.001,
            "mission": mission,
            "initial_state": {
                "hazard_level": 4,
                "locations": {
                    "Town Square": {"description": "A flooded square", "nearby": ["Hill"], "items": []},
                    "Hill": {"description": "High ground", "nearby": ["Town Square"], "items": []},
                },
            },
        },
        "agent_templates": [
            {
                "name": "Ada",
                "role": "human",
                "model_id": "test-model",
                "provider": "ollama",
                "persona": {
                    "name": "Ada", "age": 30, "sex": "female", "occupation": "Nurse",
                    "location": "Town Square",
                },
            }
        ],
    }


def _act_json() -> str:
    return json.dumps({
        "action": "She hurries toward the hill.",
        "speech": "We need high ground!",
        "thought": "The water is rising.",
        "emotion": "fear",
        "move_to": "Hill",
        "stress_level": 6,
    })


def _think_json() -> str:
    return json.dumps({"urgency": "medium", "assessment": "Water is rising", "top_need": "shelter"})


def _plan_json() -> str:
    return json.dumps({"goal": "Reach high ground", "steps": ["Move to Hill"], "success_criteria": "Safe", "fallback": None})


def _mock_generate(**kwargs) -> LLMResponse:
    system = kwargs.get("system") or ""
    if "analyzing a situation" in system:
        return LLMResponse(content=_think_json())
    if "creating an action plan" in system:
        return LLMResponse(content=_plan_json())
    return LLMResponse(content=_act_json())


# ---------------------------------------------------------------------------
# Governance: keyword classifier path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_governance_flags_ethically_significant_action(db_session):
    """An action matching an ethical pattern is flagged pending + emits event."""
    run = Run(id="run-gov-1", scenario_id="scenario-gov", status=RunStatus.PENDING)
    db_session.add(run)
    await db_session.commit()

    events: list[tuple[str, dict]] = []
    with patch(
        "emotionsim.simulation.engine.get_settings",
        return_value=Settings(governance_enabled=True),
    ):
        engine = SimulationEngine(
            run_id="run-gov-1", db_session=db_session,
            on_event=lambda t, d: events.append((t, d)),
        )
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(_scenario_config())

    agent = next(a for a in engine.agents.values() if a.role == "human")
    agent._last_cinematic = {
        "action": "She abandons the injured child and leaves her behind.",
        "thought": "I can't carry her.",
    }
    response = AgentResponse(actions=[], message=None, state_changes={}, reasoning="I can't carry her.")

    await engine._evaluate_governance(agent.id, agent, response)

    assert agent.id in engine._governance_flags
    decision = engine._governance_flags[agent.id]
    assert "abandoning_injured_or_vulnerable" in decision["categories"]
    assert any(t == "governance_pending" for t, _ in events)


@pytest.mark.asyncio
async def test_governance_warning_appears_in_agent_prompt():
    """The flagged decision surfaces as a governance warning in build_context."""
    agent = HumanAgent(name="Ada", persona=_persona())
    gov = {"categories": ["abandoning_injured_or_vulnerable"], "significance": 0.8}

    context = agent.build_context(
        {
            "hazard_level": 5,
            "current_step": 3,
            "locations": {"Town Square": {"nearby": ["Hill"], "items": []}},
            "agents": {},
            "governance": gov,
        },
        messages=[],
    )
    assert "GOVERNANCE WARNING" in context
    assert "abandoning_injured_or_vulnerable" in context


# ---------------------------------------------------------------------------
# Governance: config-gated LLM scorer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_governance_llm_scorer_denies_action(db_session):
    """With use_llm_scorer=True, the LLM resolves a flagged action."""
    run = Run(id="run-gov-2", scenario_id="scenario-gov", status=RunStatus.PENDING)
    db_session.add(run)
    await db_session.commit()

    events: list[tuple[str, dict]] = []
    with patch(
        "emotionsim.simulation.engine.get_settings",
        return_value=Settings(governance_enabled=True, governance_use_llm_scorer=True),
    ):
        engine = SimulationEngine(
            run_id="run-gov-2", db_session=db_session,
            on_event=lambda t, d: events.append((t, d)),
        )
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(_scenario_config())

    agent = next(a for a in engine.agents.values() if a.role == "human")
    agent._last_cinematic = {
        "action": "He takes all the food and hides it for himself.",
        "thought": "I need this more than them.",
    }
    response = AgentResponse(actions=[], message=None, state_changes={}, reasoning="I need this.")

    def _scorer(**kwargs):
        return LLMResponse(content=json.dumps({
            "significance": 0.9, "approved": False, "note": "Hoarding endangers the group.",
        }))

    with patch("emotionsim.agents.human.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_scorer)):
        await engine._evaluate_governance(agent.id, agent, response)

    assert agent.id in engine._governance_flags  # denied -> warning
    resolved = [d for t, d in events if t == "governance_resolved"]
    assert resolved and resolved[0]["decision"]["approved"] is False
    audit = engine.governance.get_audit_log()
    assert audit and audit[-1].status.value == "denied"


@pytest.mark.asyncio
async def test_governance_llm_scorer_approves_action(db_session):
    """An LLM-approved flagged action produces no agent warning."""
    run = Run(id="run-gov-3", scenario_id="scenario-gov", status=RunStatus.PENDING)
    db_session.add(run)
    await db_session.commit()

    with patch(
        "emotionsim.simulation.engine.get_settings",
        return_value=Settings(governance_enabled=True, governance_use_llm_scorer=True),
    ):
        engine = SimulationEngine(run_id="run-gov-3", db_session=db_session)
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(_scenario_config())

    agent = next(a for a in engine.agents.values() if a.role == "human")
    agent._last_cinematic = {
        "action": "She risks her own life to save the child from the flood.",
        "thought": "I have to try.",
    }
    response = AgentResponse(actions=[], message=None, state_changes={}, reasoning="I have to try.")

    def _scorer(**kwargs):
        return LLMResponse(content=json.dumps({
            "significance": 0.3, "approved": True, "note": "Courageous, acceptable.",
        }))

    with patch("emotionsim.agents.human.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_scorer)):
        await engine._evaluate_governance(agent.id, agent, response)

    assert agent.id not in engine._governance_flags  # approved -> no warning


# ---------------------------------------------------------------------------
# Goal tree
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_goal_tree_setup_at_initialize(db_session):
    """initialize() builds mission -> group -> individual goals."""
    run = Run(id="run-gt-1", scenario_id="scenario-gt", status=RunStatus.PENDING)
    db_session.add(run)
    await db_session.commit()

    with patch(
        "emotionsim.simulation.engine.get_settings",
        return_value=Settings(goal_tree_enabled=True),
    ):
        engine = SimulationEngine(run_id="run-gt-1", db_session=db_session)
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(_scenario_config(mission="Save everyone you can"))

    assert engine.goal_tree.mission is not None
    assert engine.goal_tree.mission.description == "Save everyone you can"

    agent = next(a for a in engine.agents.values() if a.role == "human")
    ctx = engine.goal_tree.get_context_string(agent.id)
    assert "MISSION: Save everyone you can" in ctx
    assert "GROUP GOAL" in ctx
    assert "YOUR GOAL" in ctx


def test_goal_chain_appears_in_agent_prompt():
    """The goal chain is surfaced in build_context alongside plan context."""
    agent = HumanAgent(name="Ada", persona=_persona())
    goal_ctx = (
        "MISSION: Save everyone you can\n"
        "  GROUP GOAL: Survive and support each other\n"
        "    YOUR GOAL [ACTIVE] (priority 5): Survive"
    )
    context = agent.build_context(
        {
            "hazard_level": 5,
            "current_step": 3,
            "locations": {"Town Square": {"nearby": ["Hill"], "items": []}},
            "agents": {},
            "goal_tree": goal_ctx,
        },
        messages=[],
    )
    assert "MISSION: Save everyone you can" in context
    assert "YOUR GOAL [ACTIVE]" in context


# ---------------------------------------------------------------------------
# Full V1 run with governance enabled (default)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v1_run_completes_with_governance_enabled(db_session):
    """A full run completes with governance_enabled=True (default config)."""
    run = Run(id="run-gov-run", scenario_id="scenario-gov", status=RunStatus.PENDING)
    db_session.add(run)
    await db_session.commit()

    with patch(
        "emotionsim.simulation.engine.get_settings",
        return_value=Settings(governance_enabled=True, goal_tree_enabled=True),
    ):
        engine = SimulationEngine(run_id="run-gov-run", db_session=db_session)
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(_scenario_config(max_steps=2))

    for agent in engine.agents.values():
        agent.should_respond = lambda *a, **k: True

    with patch("emotionsim.agents.human.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_mock_generate)), \
         patch("emotionsim.agents.base.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_mock_generate)):
        await engine.start()

    assert engine.current_step == 2
    assert engine.governance is not None
    assert engine.goal_tree.mission is not None

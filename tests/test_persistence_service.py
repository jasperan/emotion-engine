"""Step 7: engine refactor — persistence service + step-event payload builder.

The SimulationEngine delegates Step/Run/Message writes to RunPersistence and
step_completed payload construction to build_step_completed_payload. These
tests verify the extracted services behave identically to the inline logic
they replaced, and that the engine still writes everything end-to-end.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from emotionsim.models.message import Message
from emotionsim.models.run import Run, RunStatus
from emotionsim.models.step import Step
from emotionsim.schemas.agent import AgentMessage
from emotionsim.simulation.persistence import RunPersistence
from emotionsim.simulation.step_events import build_step_completed_payload


@pytest.mark.asyncio
async def test_persistence_saves_step(db_session):
    await RunPersistence(db_session).save_step(
        run_id="run-p1",
        step_index=3,
        world_state={"hazard_level": 5},
        actions=[{"action_type": "move"}],
        step_metrics={"actions": 1},
    )
    await db_session.commit()

    rows = (await db_session.execute(
        select(Step).where(Step.run_id == "run-p1")
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].step_index == 3
    assert rows[0].state_snapshot == {"hazard_level": 5}


@pytest.mark.asyncio
async def test_persistence_updates_run_progress(db_session):
    db_session.add(Run(id="run-p2", scenario_id="scenario-p", status=RunStatus.RUNNING))
    await db_session.commit()

    await RunPersistence(db_session).update_run_progress(
        run_id="run-p2", current_step=7, world_state={"hazard_level": 8}
    )
    await db_session.commit()

    run = await db_session.get(Run, "run-p2")
    assert run.current_step == 7
    assert run.world_state == {"hazard_level": 8}


@pytest.mark.asyncio
async def test_persistence_saves_message_with_conversation(db_session):
    msg = AgentMessage(
        content="Hold on!",
        to_target="broadcast",
        message_type="broadcast",
    )
    # conversation_id overrides the stored type to "conversation" (engine behavior)
    await RunPersistence(db_session).save_message(
        run_id="run-p3",
        agent_id="agent-1",
        msg=msg,
        step_index=4,
        conversation_id="conv-1",
    )
    await db_session.commit()

    rows = (await db_session.execute(
        select(Message).where(Message.run_id == "run-p3")
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].message_type.value == "conversation"
    assert rows[0].to_target == "conv-1"
    assert rows[0].msg_metadata == {"conversation_id": "conv-1"}


@pytest.mark.asyncio
async def test_persistence_completes_run(db_session):
    db_session.add(Run(id="run-p4", scenario_id="scenario-p", status=RunStatus.RUNNING))
    await db_session.commit()

    await RunPersistence(db_session).complete_run(
        run_id="run-p4",
        metrics={"steps": 10},
        evaluation={"scores": {}},
    )

    run = await db_session.get(Run, "run-p4")
    assert run.status == RunStatus.COMPLETED
    assert run.metrics == {"steps": 10}
    assert run.evaluation == {"scores": {}}
    assert run.completed_at is not None


def test_step_completed_payload_builder():
    payload = build_step_completed_payload(
        step=5,
        actions=[{"a": 1}],
        messages=[{"m": 1}],
        world_state={"hazard_level": 5},
        conversations=[],
        agent_telemetry={"x": {}},
        world_state_diff={},
        negotiations={},
        emotion_contagion={},
        social_dynamics={},
        governance_pending=[{"id": "d1"}],
        goal_tree={"mission_id": "m1"},
    )
    assert payload["step"] == 5
    assert payload["governance_pending"] == [{"id": "d1"}]
    assert payload["goal_tree"] == {"mission_id": "m1"}
    assert payload["social_dynamics"] == {}

    # Optional governance/goal-tree keys omitted when not provided
    payload_min = build_step_completed_payload(
        step=1, actions=[], messages=[], world_state={}, conversations=[],
        agent_telemetry={}, world_state_diff={}, negotiations={},
        emotion_contagion={}, social_dynamics={},
    )
    assert "governance_pending" not in payload_min


@pytest.mark.asyncio
async def test_engine_still_persists_end_to_end(db_session):
    """After the refactor, a full run still writes steps + messages + completion."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from emotionsim.core.config import Settings
    from emotionsim.simulation.engine import SimulationEngine

    db_session.add(Run(id="run-p5", scenario_id="scenario-p", status=RunStatus.PENDING))
    await db_session.commit()

    config = {
        "config": {
            "max_steps": 1,
            "tick_delay": 0.001,
            "seed": 1,
            "initial_state": {
                "hazard_level": 4,
                "locations": {
                    "Town Square": {"description": "A square", "nearby": ["Hill"], "items": []},
                    "Hill": {"description": "High ground", "nearby": ["Town Square"], "items": []},
                },
            },
        },
        "agent_templates": [
            {
                "name": "Ada", "role": "human", "model_id": "test-model", "provider": "ollama",
                "persona": {"name": "Ada", "age": 30, "sex": "female", "occupation": "Nurse",
                            "location": "Town Square"},
            }
        ],
    }

    import json
    from emotionsim.llm.base import LLMResponse

    def _mock_generate(**kwargs):
        system = kwargs.get("system") or ""
        if "analyzing a situation" in system:
            content = {"urgency": "medium", "assessment": "Water rising", "top_need": "shelter"}
        elif "creating an action plan" in system:
            content = {"goal": "Reach high ground", "steps": ["Move to Hill"], "success_criteria": "Safe", "fallback": None}
        else:
            content = {"action": "She hurries to the hill.", "speech": "Move!", "thought": "Rising.",
                       "emotion": "fear", "move_to": "Hill", "stress_level": 6}
        return LLMResponse(content=json.dumps(content))

    with patch("emotionsim.simulation.engine.get_settings", return_value=Settings()):
        engine = SimulationEngine(run_id="run-p5", db_session=db_session)
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(config)

    for agent in engine.agents.values():
        agent.should_respond = lambda *a, **k: True

    with patch("emotionsim.agents.human.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_mock_generate)), \
         patch("emotionsim.agents.base.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_mock_generate)):
        await engine.start()

    run = await db_session.get(Run, "run-p5")
    assert run.status == RunStatus.COMPLETED
    assert run.current_step == 1
    steps = (await db_session.execute(
        select(Step).where(Step.run_id == "run-p5")
    )).scalars().all()
    assert len(steps) == 1
    messages = (await db_session.execute(
        select(Message).where(Message.run_id == "run-p5")
    )).scalars().all()
    assert len(messages) >= 1

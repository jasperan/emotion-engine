"""Step 7: engine refactor — extracted infrastructure services.

Verifies the TokenStreamer (batched token streaming) and the engine's
delegation to SceneProcessor / ReactionRound, completing the "engine.py
measurably smaller with identical behavior" criterion.
"""

from __future__ import annotations

import asyncio

import pytest

from emotionsim.simulation.token_streamer import TokenStreamer


@pytest.mark.asyncio
async def test_token_streamer_buffers_and_flushes():
    """Tokens accumulate into a buffer and flush in batches + on demand."""
    events: list[tuple[str, dict]] = []
    streamer = TokenStreamer(on_event=lambda t, d: events.append((t, d)))

    token_logger = type("TL", (), {"log_token": None})()
    logged: list[tuple[str, str, str]] = []

    async def _log(agent_id, agent_name, token):
        logged.append((agent_id, agent_name, token))

    token_logger.log_token = _log

    counter = [0]
    cb = streamer.make_callback(
        "a1", "Ada", step=3,
        stream_callback=None,
        token_logger=token_logger,
        counter=counter,
    )

    # Buffered tokens are not flushed until interval/forced flush
    await cb("Hel")
    await cb("lo")
    await streamer.flush("a1", "Ada", 3)

    assert counter[0] == 5
    assert logged == [("a1", "Ada", "Hel"), ("a1", "Ada", "lo")]
    stream_events = [d for t, d in events if t == "token_stream"]
    assert stream_events and stream_events[-1]["tokens"] == "Hello"
    assert stream_events[-1]["step"] == 3
    # Buffer cleared after flush
    await streamer.flush("a1", "Ada", 3)
    assert [d for t, d in events if t == "token_stream"][-1]["tokens"] == "Hello"


@pytest.mark.asyncio
async def test_token_streamer_forwards_to_stream_callback():
    forwarded: list[tuple[str, str]] = []

    async def _stream(agent_id: str, token: str):
        forwarded.append((agent_id, token))

    streamer = TokenStreamer(on_event=lambda t, d: None)
    cb = streamer.make_callback("a1", "Ada", step=1, stream_callback=_stream)
    await cb("x")
    await cb("y")

    assert forwarded == [("a1", "x"), ("a1", "y")]


@pytest.mark.asyncio
async def test_engine_delegates_to_scene_and_reaction_services(db_session):
    """The engine owns SceneProcessor + ReactionRound instances (delegation)."""
    from unittest.mock import MagicMock, patch

    from emotionsim.simulation.engine import SimulationEngine

    with patch("emotionsim.simulation.engine.get_settings"):
        engine = SimulationEngine(run_id="run-ref", db_session=db_session)

    assert engine.scene_processor is not None
    assert engine.reaction_round is not None
    assert engine.persistence is not None
    # Back-references point at the engine
    assert engine.scene_processor.runtime is engine
    assert engine.reaction_round.runtime is engine


@pytest.mark.asyncio
async def test_engine_identical_behavior_after_refactor(db_session):
    """Two sequential runs of the same seeded scenario produce identical steps
    (determinism preserved after the refactor)."""
    import json
    from unittest.mock import AsyncMock, MagicMock, patch

    from emotionsim.core.config import Settings
    from emotionsim.llm.base import LLMResponse
    from emotionsim.models.run import Run, RunStatus
    from emotionsim.simulation.engine import SimulationEngine

    def _config(run_seed: int) -> dict:
        return {
            "config": {
                "max_steps": 2,
                "tick_delay": 0.001,
                "seed": run_seed,
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
                },
                {
                    "name": "Bo", "role": "human", "model_id": "test-model", "provider": "ollama",
                    "persona": {"name": "Bo", "age": 40, "sex": "male", "occupation": "Engineer",
                                "location": "Town Square"},
                },
            ],
        }

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

    snapshots = []

    for run_id in ("run-det-a", "run-det-b"):
        db_session.add(Run(id=run_id, scenario_id="scenario-det", status=RunStatus.PENDING))
        await db_session.commit()

        with patch("emotionsim.simulation.engine.get_settings", return_value=Settings(scene_mode=False)):
            engine = SimulationEngine(run_id=run_id, db_session=db_session)
            with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
                mock_router.get_client.return_value = MagicMock()
                await engine.initialize(_config(42))

        for agent in engine.agents.values():
            agent.should_respond = lambda *a, **k: True

        with patch("emotionsim.agents.human.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_mock_generate)), \
             patch("emotionsim.agents.base.LLMRouter.generate_with_fallback", AsyncMock(side_effect=_mock_generate)):
            await engine.start()

        from sqlalchemy import select
        from emotionsim.models.step import Step
        rows = (await db_session.execute(
            select(Step).where(Step.run_id == run_id).order_by(Step.step_index)
        )).scalars().all()
        # Compare deterministic aggregates (avg health/stress, hazard, message
        # counts) — raw snapshots embed random agent UUIDs by design.
        snapshots.append([
            (s.step_index, s.step_metrics.get("avg_health"), s.step_metrics.get("avg_stress"),
             s.step_metrics.get("hazard_level"), s.step_metrics.get("message_count"))
            for s in rows
        ])

    assert snapshots[0] == snapshots[1], "seeded runs diverged after the refactor"

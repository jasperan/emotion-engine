"""Step 9: observability — run metrics endpoint, datalake compare, metrics telemetry."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from emotionsim.models.run import Run, RunStatus


# ---------------------------------------------------------------------------
# Engine completion augments run.metrics with cost/latency/tokens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_completion_augments_metrics(db_session):
    """A completed run's metrics include tokens / latency / cost telemetry."""
    from unittest.mock import AsyncMock as _A, MagicMock as _M

    from emotionsim.core.config import Settings
    from emotionsim.llm.base import LLMResponse
    from emotionsim.simulation.engine import SimulationEngine

    db_session.add(Run(id="run-m1", scenario_id="scenario-m", status=RunStatus.PENDING))
    await db_session.commit()

    config = {
        "config": {
            "max_steps": 1,
            "tick_delay": 0.001,
            "seed": 3,
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

    async def _mock_generate(**kwargs):
        system = kwargs.get("system") or ""
        if "analyzing a situation" in system:
            content = {"urgency": "medium", "assessment": "Water rising", "top_need": "shelter"}
        elif "creating an action plan" in system:
            content = {"goal": "Reach high ground", "steps": ["Move to Hill"], "success_criteria": "Safe", "fallback": None}
        else:
            content = {"action": "She hurries to the hill.", "speech": "Move!", "thought": "Rising.",
                       "emotion": "fear", "move_to": "Hill", "stress_level": 6}
        # Stream a few tokens so the engine's token accounting records them
        stream_cb = kwargs.get("stream_callback")
        if stream_cb is not None:
            for tok in ("She ", "hurries", " to ", "the ", "hill. "):
                await stream_cb(tok)
        return LLMResponse(content=json.dumps(content))

    with patch("emotionsim.simulation.engine.get_settings",
               return_value=Settings(llm_cost_per_1k_tokens=0.5)):
        engine = SimulationEngine(run_id="run-m1", db_session=db_session)
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(config)

    for agent in engine.agents.values():
        agent.should_respond = lambda *a, **k: True

    with patch("emotionsim.agents.human.LLMRouter.generate_with_fallback", _A(side_effect=_mock_generate)), \
         patch("emotionsim.agents.base.LLMRouter.generate_with_fallback", _A(side_effect=_mock_generate)):
        await engine.start()

    run = await db_session.get(Run, "run-m1")
    assert run.metrics is not None
    assert "tokens" in run.metrics
    assert run.metrics["tokens"] >= 1
    assert "tokens_per_agent" in run.metrics
    assert "latency_ms" in run.metrics
    assert "cost_estimate_usd" in run.metrics
    # 0.5 per 1k chars
    assert run.metrics["cost_estimate_usd"] == round(run.metrics["tokens"] / 1000.0 * 0.5, 6)


# ---------------------------------------------------------------------------
# /api/runs/{id}/metrics endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_metrics_endpoint(db_session):
    """GET /api/runs/{id}/metrics returns the run's persisted telemetry."""
    from emotionsim.api.runs import get_run_metrics

    db_session.add(Run(
        id="run-m2", scenario_id="scenario-m", status=RunStatus.COMPLETED,
        current_step=5,
        metrics={"tokens": 1200, "latency_ms": 42.5, "cost_estimate_usd": 0.6,
                 "avg_stress": 6.0, "avg_health": 7.5},
    ))
    await db_session.commit()

    response = await get_run_metrics("run-m2", db_session)

    assert response["run_id"] == "run-m2"
    assert response["status"] == "completed"
    assert response["current_step"] == 5
    assert response["metrics"]["tokens"] == 1200
    assert response["metrics"]["cost_estimate_usd"] == 0.6


@pytest.mark.asyncio
async def test_run_metrics_endpoint_404(db_session):
    from emotionsim.api.runs import get_run_metrics

    with pytest.raises(HTTPException) as exc:
        await get_run_metrics("run-missing", db_session)
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# /datalake/compare endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_datalake_compare_endpoint():
    """compare_runs pivots metrics across runs: metric -> {run_id: value}."""
    from emotionsim.api.datalake import compare_runs

    store = MagicMock()
    # Datalake endpoints call _run_sync (asyncio.to_thread) — sync methods.
    store.get_run_metrics = MagicMock(side_effect=[
        [{"metric_name": "avg_stress", "metric_value": 6.0},
         {"metric_name": "cooperation", "metric_value": 0.7}],
        [{"metric_name": "avg_stress", "metric_value": 4.5}],
    ])
    store.close = MagicMock()

    with patch("emotionsim.api.datalake._get_store", return_value=store):
        result = await compare_runs("run-a,run-b")

    assert result["run_ids"] == ["run-a", "run-b"]
    assert result["total_metrics"] == 2
    assert result["metrics"]["avg_stress"] == {"run-a": 6.0, "run-b": 4.5}
    # metric only present in one run shows None for the other
    assert result["metrics"]["cooperation"] == {"run-a": 0.7, "run-b": None}
    store.close.assert_called_once()


@pytest.mark.asyncio
async def test_datalake_compare_requires_ids():
    from emotionsim.api.datalake import compare_runs

    store = MagicMock()
    store.close = MagicMock()
    with patch("emotionsim.api.datalake._get_store", return_value=store):
        with pytest.raises(HTTPException) as exc:
            await compare_runs("   , ,")
    assert exc.value.status_code == 400

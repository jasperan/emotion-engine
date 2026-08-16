"""Offline eval harness: scenario × seed matrices against the stub LLM (Step 8).

Runs full simulations headlessly (zero network), aggregates cooperation /
emergence / determinism metrics, and detects determinism regressions.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Callable
from unittest.mock import MagicMock, patch

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from emotionsim.core.config import Settings
from emotionsim.core.database import Base
from emotionsim.eval.metrics import compute_run_metrics, run_fingerprint
from emotionsim.scenarios.rising_flood import get_rising_flood_config
from emotionsim.scenarios.space_station import get_space_station_config
from emotionsim.scenarios.bushfire import get_bushfire_config
from emotionsim.scenarios.sinking_ship import get_sinking_ship_config

logger = logging.getLogger(__name__)

#: scenario name -> config factory (dict shape accepted by engine.initialize)
SCENARIO_REGISTRY: dict[str, Callable[[], dict[str, Any]]] = {
    "Rising Flood": get_rising_flood_config,
    "Space Station": get_space_station_config,
    "Bushfire": get_bushfire_config,
    "Sinking Ship": get_sinking_ship_config,
}


def list_scenarios() -> list[str]:
    return sorted(SCENARIO_REGISTRY)


def _stub_settings(max_steps: int) -> Settings:
    """Offline eval settings: stub LLM backend, sequential, deterministic."""
    return Settings(
        llm_backend="stub",
        scene_mode=False,
        max_concurrent_llm_calls=1,
        graph_memory_enabled=False,
        governance_enabled=True,
        goal_tree_enabled=True,
        default_max_steps=max_steps,
    )


async def _run_single(
    db: AsyncSession,
    scenario_name: str,
    config: dict[str, Any],
    seed: int,
    max_steps: int,
    prompt_variant: str = "default",
) -> dict[str, Any]:
    """Run one scenario × seed × prompt-variant against the stub LLM."""
    settings = _stub_settings(max_steps)
    step_payloads: list[dict[str, Any]] = []
    events: list[tuple[str, dict]] = []

    def _on_event(event_type: str, data: dict) -> None:
        events.append((event_type, data))
        if event_type == "step_completed":
            step_payloads.append(data)

    run_config = {
        # engine.initialize reads the seed from the TOP level
        "seed": seed,
        "config": {
            **config.get("config", {}),
            "max_steps": max_steps,
            "tick_delay": 0.001,
            "seed": seed,
        },
        "agent_templates": config.get("agent_templates", []),
    }
    # Prompt variant: injected as an experiment instruction into agent prompts
    if prompt_variant and prompt_variant != "default":
        initial = run_config["config"].setdefault("initial_state", {})
        initial["_prompt_variant"] = f"personality emphasis: {prompt_variant}"

    with patch("emotionsim.simulation.engine.get_settings", return_value=settings), \
         patch("emotionsim.core.config.get_settings", return_value=settings):
        from emotionsim.simulation.engine import SimulationEngine

        engine = SimulationEngine(
            run_id=f"eval-{scenario_name}-{seed}-{uuid.uuid4().hex[:8]}",
            db_session=db,
            on_event=_on_event,
        )
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(run_config)

        # Deterministic: every agent responds when gated
        for agent in engine.agents.values():
            agent.should_respond = lambda *a, **k: True

        await engine.start()

    metrics = compute_run_metrics(engine, step_payloads)
    metrics["scenario"] = scenario_name
    metrics["seed"] = seed
    metrics["prompt_variant"] = prompt_variant
    metrics["fingerprint"] = run_fingerprint(step_payloads)
    metrics["agents"] = len(engine.agents)
    return metrics


async def run_matrix(
    scenario_names: list[str],
    seeds: list[int],
    max_steps: int,
    prompt_variants: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run scenario × seed × prompt-variant matrix headlessly."""
    variants = prompt_variants or ["default"]
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    results: list[dict[str, Any]] = []
    async with session_factory() as db:
        for scenario_name in scenario_names:
            factory = SCENARIO_REGISTRY.get(scenario_name)
            if factory is None:
                raise ValueError(
                    f"Unknown scenario '{scenario_name}'. Available: {list_scenarios()}"
                )
            config = factory()
            for variant in variants:
                for seed in seeds:
                    logger.info("eval: %s seed=%d variant=%s", scenario_name, seed, variant)
                    results.append(await _run_single(
                        db, scenario_name, config, seed, max_steps, prompt_variant=variant
                    ))

    await engine.dispose()
    return results


def check_determinism(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return violations: runs with identical (scenario, seed, variant) whose
    fingerprints differ."""
    by_key: dict[tuple[str, int, str], list[str]] = {}
    for r in results:
        key = (r["scenario"], r["seed"], r.get("prompt_variant", "default"))
        by_key.setdefault(key, []).append(r["fingerprint"])

    violations = []
    for (scenario, seed, variant), fps in by_key.items():
        if len(fps) >= 2 and len(set(fps)) > 1:
            violations.append({
                "scenario": scenario,
                "seed": seed,
                "prompt_variant": variant,
                "fingerprints": fps,
            })
    return violations


async def run_eval(
    scenario_names: list[str] | None = None,
    seeds: int = 3,
    max_steps: int = 10,
    repeat: int = 2,
    prompt_variants: list[str] | None = None,
) -> dict[str, Any]:
    """High-level entry: runs the matrix (+ determinism repeat) and returns
    a summary dict with results + violations."""
    names = scenario_names or list_scenarios()[:2]
    seed_values = list(range(1, seeds + 1))
    variants = prompt_variants or ["default"]

    # Determinism check: run each (scenario, seed, variant) twice
    results: list[dict[str, Any]] = []
    for _ in range(repeat):
        results.extend(await run_matrix(names, seed_values, max_steps, variants))

    violations = check_determinism(results)

    # Aggregate per scenario (across variants + seeds)
    per_scenario: dict[str, dict[str, float]] = {}
    for r in results:
        s = per_scenario.setdefault(r["scenario"], {
            "cooperation": 0.0, "runs": 0,
        })
        s["cooperation"] += r["cooperation_score"]
        s["runs"] += 1
    for s in per_scenario.values():
        s["cooperation_avg"] = round(s["cooperation"] / max(s["runs"], 1), 4)
        del s["cooperation"]

    return {
        "scenarios": names,
        "seeds": seed_values,
        "prompt_variants": variants,
        "max_steps": max_steps,
        "repeats": repeat,
        "run_count": len(results),
        "per_scenario": per_scenario,
        "determinism_violations": violations,
        "deterministic": len(violations) == 0,
        "results": results,
    }

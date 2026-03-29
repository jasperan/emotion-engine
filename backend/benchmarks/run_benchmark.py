"""
Benchmark runner: launches N simulations in parallel and tracks run IDs.
Results are persisted in Oracle DB and indexed in a local manifest.
"""
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import Base
from app.models.scenario import Scenario
from app.models.run import Run, RunStatus
from app.simulation.engine import SimulationEngine


BENCHMARK_DIR = Path(__file__).parent / "results"
BENCHMARK_DIR.mkdir(exist_ok=True)

# 5 diverse scenarios covering different disaster types and group dynamics
BENCHMARK_SCENARIOS = [
    {"name": "Rising Flood (10 agents)", "seed": 42, "max_steps": 8},
    {"name": "Airplane Crash Investigation (10 agents)", "seed": 101, "max_steps": 8},
    {"name": "Australian Bushfire Encirclement (12 agents)", "seed": 202, "max_steps": 8},
    {"name": "Mass Casualty: Building Collapse (10 agents)", "seed": 303, "max_steps": 8},
    {"name": "Philippines Mega-Tsunami (12 agents)", "seed": 404, "max_steps": 8},
]


async def run_single_sim(
    scenario_name: str,
    seed: int,
    max_steps: int,
    session_factory,
    run_index: int,
) -> dict:
    """Run one simulation and return summary metadata."""
    t0 = time.time()
    print(f"[SIM-{run_index}] Starting: {scenario_name} (seed={seed}, steps={max_steps})", flush=True)

    async with session_factory() as db:
        # Load scenario
        result = await db.execute(
            select(Scenario).where(Scenario.name == scenario_name)
        )
        scenario = result.scalars().first()
        if not scenario:
            return {"error": f"Scenario not found: {scenario_name}"}

        # Create run
        run = Run(
            scenario_id=scenario.id,
            max_steps=max_steps,
            seed=seed,
            status=RunStatus.PENDING,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        run_id = run.id
        print(f"[SIM-{run_index}] Run ID: {run_id}", flush=True)

        # Create engine (matches CLI pattern: run_id + db_session)
        engine = SimulationEngine(
            run_id=run.id,
            db_session=db,
        )

        # Build config from scenario (matches CLI pattern)
        # Override all agent model_ids to use a single model
        # (avoids GPU OOM from loading multiple models concurrently)
        unified_model = get_settings().ollama_default_model
        templates = []
        for t in scenario.agent_templates:
            t_copy = dict(t)
            t_copy["model_id"] = unified_model
            templates.append(t_copy)

        config = {
            "config": scenario.config,
            "agent_templates": templates,
            "seed": seed,
        }
        config["config"]["max_steps"] = max_steps

        await engine.initialize(config)
        print(f"[SIM-{run_index}] Initialized {len(engine.agents)} agents", flush=True)

        try:
            await engine.start()
        except Exception as e:
            print(f"[SIM-{run_index}] Engine error: {e}")
            run.status = RunStatus.FAILED
            await db.commit()

        # Refresh to get final state
        await db.refresh(run)

        elapsed = time.time() - t0
        print(f"[SIM-{run_index}] Completed in {elapsed:.1f}s — status={run.status.value}, steps={run.current_step}", flush=True)

        return {
            "run_id": run_id,
            "scenario": scenario_name,
            "seed": seed,
            "max_steps": max_steps,
            "final_step": run.current_step,
            "status": run.status.value,
            "elapsed_seconds": round(elapsed, 1),
            "metrics": run.metrics or {},
            "evaluation": run.evaluation or {},
        }


async def main():
    settings = get_settings()
    db_engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    # Ensure tables exist
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print(f"Running {len(BENCHMARK_SCENARIOS)} benchmark simulations sequentially")
    print(f"(Ollama can only serve one GPU request at a time)\n")

    # Run sequentially to avoid overwhelming Ollama
    results = []
    for i, cfg in enumerate(BENCHMARK_SCENARIOS):
        try:
            result = await run_single_sim(
                scenario_name=cfg["name"],
                seed=cfg["seed"],
                max_steps=cfg["max_steps"],
                session_factory=session_factory,
                run_index=i,
            )
            results.append(result)
        except Exception as e:
            results.append(e)

    # Process results
    manifest = {
        "benchmark_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "model": settings.ollama_default_model,
        "backend": settings.llm_backend,
        "runs": [],
    }

    for i, r in enumerate(results):
        if isinstance(r, Exception):
            manifest["runs"].append({
                "scenario": BENCHMARK_SCENARIOS[i]["name"],
                "error": str(r),
            })
        else:
            manifest["runs"].append(r)

    # Save manifest
    manifest_path = BENCHMARK_DIR / f"benchmark_{manifest['benchmark_id']}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nManifest saved: {manifest_path}")

    # Print summary table
    print(f"\n{'='*80}")
    print(f"{'Scenario':<45} {'Status':<12} {'Steps':<8} {'Time':<10}")
    print(f"{'='*80}")
    for run in manifest["runs"]:
        name = run.get("scenario", "?")[:44]
        status = run.get("status", run.get("error", "?"))[:11]
        steps = str(run.get("final_step", "-"))
        elapsed = f"{run.get('elapsed_seconds', 0)}s"
        print(f"{name:<45} {status:<12} {steps:<8} {elapsed:<10}")
    print(f"{'='*80}")

    await db_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

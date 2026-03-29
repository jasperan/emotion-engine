"""
Benchmark runner: runs simulations across multiple models for comparison.
Uses the CLI directly (which handles Ollama model loading gracefully).
Results are persisted in Oracle DB and indexed in local manifest JSON.
"""
import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


BENCHMARK_DIR = Path(__file__).parent / "results"
BENCHMARK_DIR.mkdir(exist_ok=True)

# Models to benchmark
BENCHMARK_MODELS = [
    "qwen3.5:9b",
    "qwen3.5:4b",
    "gemma3:latest",
]

# 5 diverse scenarios (same seeds for reproducibility across models)
BENCHMARK_SCENARIOS = [
    {"name": "Rising Flood (10 agents)", "seed": 42, "max_steps": 8},
    {"name": "Airplane Crash Investigation (10 agents)", "seed": 101, "max_steps": 8},
    {"name": "Australian Bushfire Encirclement (12 agents)", "seed": 202, "max_steps": 8},
    {"name": "Mass Casualty: Building Collapse (10 agents)", "seed": 303, "max_steps": 8},
    {"name": "Philippines Mega-Tsunami (12 agents)", "seed": 404, "max_steps": 8},
]


def swap_ollama_model(model_name: str) -> bool:
    """Unload all models, then preload the target model."""
    print(f"\n{'─'*60}", flush=True)
    print(f"Swapping Ollama to: {model_name}", flush=True)

    # Stop all loaded models
    try:
        result = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if parts:
                loaded = parts[0]
                subprocess.run(
                    ["ollama", "stop", loaded],
                    capture_output=True, timeout=10,
                )
                print(f"  Stopped: {loaded}", flush=True)
    except Exception as e:
        print(f"  Warning stopping models: {e}", flush=True)

    # Wait for GPU to fully free
    time.sleep(10)

    # Preload the target model
    try:
        subprocess.run(
            ["ollama", "run", model_name, "Say OK", "--nowordwrap"],
            capture_output=True, text=True, timeout=180,
        )
        time.sleep(3)
        print(f"  Loaded: {model_name}", flush=True)
        return True
    except Exception as e:
        print(f"  FAILED to load {model_name}: {e}", flush=True)
        return False


def run_sim_via_cli(
    scenario_name: str,
    seed: int,
    max_steps: int,
    model_name: str,
) -> dict:
    """Run a simulation via the CLI and capture the run ID from output."""
    # Inherit current environment, override model and concurrency settings
    env = dict(subprocess.os.environ)
    env.update({
        "OLLAMA_DEFAULT_MODEL": model_name,
        "OLLAMA_FALLBACK_MODEL": model_name,
        "MAX_CONCURRENT_LLM_CALLS": "1",
        "SCENE_MODE": "false",
        "PYTHONUNBUFFERED": "1",
    })

    cmd = [
        sys.executable, "-m", "app.cli", "run",
        "--scenario", scenario_name,
        "--max-steps", str(max_steps),
        "--seed", str(seed),
        "--simple",
    ]

    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min max per sim
            cwd=str(Path(__file__).parent.parent),
            env=env,
        )
        elapsed = time.time() - t0
        output = result.stdout + result.stderr

        # Extract run ID from output
        run_id = None
        for line in output.split("\n"):
            if "Created run:" in line:
                # Format: "✓ Created run: <uuid>"
                parts = line.split("Created run:")
                if len(parts) > 1:
                    run_id = parts[1].strip().split()[0].strip()
                    break

        status = "completed" if result.returncode == 0 else "failed"

        return {
            "run_id": run_id,
            "scenario": scenario_name,
            "model": model_name,
            "seed": seed,
            "max_steps": max_steps,
            "status": status,
            "exit_code": result.returncode,
            "elapsed_seconds": round(elapsed, 1),
        }

    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        return {
            "scenario": scenario_name,
            "model": model_name,
            "seed": seed,
            "status": "timeout",
            "elapsed_seconds": round(elapsed, 1),
            "error": "Timed out after 30 min",
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "scenario": scenario_name,
            "model": model_name,
            "status": "error",
            "elapsed_seconds": round(elapsed, 1),
            "error": str(e),
        }


def main():
    total = len(BENCHMARK_MODELS) * len(BENCHMARK_SCENARIOS)
    print(f"Benchmark: {len(BENCHMARK_MODELS)} models x {len(BENCHMARK_SCENARIOS)} scenarios = {total} runs")
    print(f"Models: {', '.join(BENCHMARK_MODELS)}", flush=True)

    all_results = []
    t_global = time.time()

    for model in BENCHMARK_MODELS:
        if not swap_ollama_model(model):
            print(f"  SKIPPING {model} (failed to load)", flush=True)
            for cfg in BENCHMARK_SCENARIOS:
                all_results.append({
                    "scenario": cfg["name"],
                    "model": model,
                    "error": "Model failed to load",
                })
            continue

        print(f"\nRunning {len(BENCHMARK_SCENARIOS)} scenarios with {model}:", flush=True)

        for i, cfg in enumerate(BENCHMARK_SCENARIOS):
            print(f"  [{i}] {cfg['name']} (seed={cfg['seed']})", flush=True)
            result = run_sim_via_cli(
                scenario_name=cfg["name"],
                seed=cfg["seed"],
                max_steps=cfg["max_steps"],
                model_name=model,
            )
            status = result.get("status", "?")
            elapsed = result.get("elapsed_seconds", 0)
            print(f"      {status} | {elapsed}s", flush=True)
            all_results.append(result)

    total_time = time.time() - t_global

    # Save manifest
    manifest = {
        "benchmark_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "models": BENCHMARK_MODELS,
        "backend": "ollama",
        "total_time_seconds": round(total_time, 1),
        "runs": all_results,
    }

    manifest_path = BENCHMARK_DIR / f"benchmark_{manifest['benchmark_id']}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nManifest saved: {manifest_path}", flush=True)

    # Print comparison table
    print(f"\n{'='*90}", flush=True)
    print(f"{'Model':<18} {'Scenario':<35} {'Status':<12} {'Time':<10}", flush=True)
    print(f"{'='*90}", flush=True)
    for r in all_results:
        model = r.get("model", "?")[:17]
        name = r.get("scenario", "?")[:34]
        status = r.get("status", r.get("error", "?"))[:11]
        elapsed = f"{r.get('elapsed_seconds', 0)}s"
        print(f"{model:<18} {name:<35} {status:<12} {elapsed:<10}", flush=True)
    print(f"{'='*90}", flush=True)
    print(f"Total time: {total_time:.0f}s ({total_time/60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()

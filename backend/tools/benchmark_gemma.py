#!/usr/bin/env python3
"""
Benchmark tool for Gemma 3 (or other models) in EmotionSim.
Runs a 1-step simulation with 10 agents and measures performance.
"""
import asyncio
import os
import sys
import time
import json
import statistics
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings, Settings
from app.simulation.engine import SimulationEngine, SimulationState
from app.llm.base import LLMResponse
from app.core.database import Base

# Global metrics collector
METRICS = {
    "start_time": 0,
    "end_time": 0,
    "requests": []
}

async def benchmark(model_name: str):
    print(f"Starting benchmark for model: {model_name} (target)")
    
    # 1. Setup in-memory DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # 2. Patch OllamaClient to measure performance
    # We need to wrap the actual generate method, not replace it entirely,
    # because we want to run the real model.
    from app.llm.ollama import OllamaClient
    original_generate = OllamaClient.generate
    
    async def measured_generate(self, *args, **kwargs):
        start = time.perf_counter()
        # Ensure model is user specified
        if "model" not in kwargs or kwargs["model"] == "gemma3" or kwargs["model"] is None:
             kwargs["model"] = model_name 
             
        try:
            # Override model in kwargs to ensure we use the requested one
            kwargs["model"] = model_name
            
            response = await original_generate(self, *args, **kwargs)
            duration = time.perf_counter() - start
            
            # Calculate tokens (approximate if raw_response usage is missing)
            usage = response.usage or {}
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
            
            METRICS["requests"].append({
                "duration": duration,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "model": kwargs["model"]
            })
            return response
        except Exception as e:
            print(f"Error in LLM call: {e}")
            raise
            
    
    # Apply patch
    with patch.object(OllamaClient, "generate", side_effect=measured_generate, autospec=True):
        
        async with AsyncSessionLocal() as session:
            # 3. Initialize Engine
            sim_engine = SimulationEngine(run_id="benchmark_run", db_session=session)
            
            # 4. Create Scenario (Airplane Crash - 10 agents)
            from app.scenarios.airplane_crash import create_airplane_crash_scenario
            scenario = create_airplane_crash_scenario(num_agents=10)
            
            # Force model for benchmark
            for agent in scenario.agent_templates:
                agent.model_id = model_name
                
            scenario_config = scenario.model_dump()
            
            # Reduce max steps to 1 for benchmark
            scenario_config["config"]["max_steps"] = 1
            
            # Initialize
            print(f"Initializing simulation with 10 agents using {model_name}...")
            await sim_engine.initialize(scenario_config)
            
            # 5. Run 1 step
            print("Running 1 step simulation...")
            METRICS["start_time"] = time.perf_counter()
            
            # We manually execute one step loop instead of start() to control it tightly
            # checking logic from engine.start -> _run_loop -> _execute_step
            
            # Override sim state to RUNNING
            sim_engine.state = SimulationState.RUNNING
            
            # Execute exactly one step
            await sim_engine._execute_step()
            
            METRICS["end_time"] = time.perf_counter()
            print("Step completed.")

    # 6. Report
    print_report()

def print_report():
    total_duration = METRICS["end_time"] - METRICS["start_time"]
    reqs = METRICS["requests"]
    num_reqs = len(reqs)
    
    if num_reqs == 0:
        print("\nNo LLM requests recorded.")
        return

    total_prompt_tokens = sum(r["prompt_tokens"] for r in reqs)
    total_completion_tokens = sum(r["completion_tokens"] for r in reqs)
    total_tokens = sum(r["total_tokens"] for r in reqs)
    
    durations = [r["duration"] for r in reqs]
    avg_latency = statistics.mean(durations)
    median_latency = statistics.median(durations)
    p95_latency = statistics.quantiles(durations, n=20)[18] if num_reqs >= 20 else max(durations)
    
    # Throughput
    # Global TPS = Total Completion Tokens / Total Duration (Sim Wall Time)
    # This represents effective system throughput
    global_tps = total_completion_tokens / total_duration if total_duration > 0 else 0
    
    # Model Speed = Average (Completion Tokens / Latency) per request
    # This represents raw model speed if serialized
    model_speeds = [r["completion_tokens"] / r["duration"] for r in reqs if r["duration"] > 0]
    avg_model_speed = statistics.mean(model_speeds) if model_speeds else 0

    print("\n" + "="*50)
    model_name = reqs[0]["model"] if reqs else "Unknown"
    print("\n" + "="*50)
    print(f"BENCHMARK REPORT: {model_name} (10 Agents, 1 Step)")
    print("="*50)
    print(f"Total Duration (Wall Time): {total_duration:.2f}s")
    print(f"Total LLM Requests:         {num_reqs}")
    print(f"Total Tokens Generated:     {total_completion_tokens}")
    print(f"Total Tokens Processed:     {total_tokens}")
    print("-" * 30)
    print(f"Avg Latency:                {avg_latency:.2f}s")
    print(f"Median Latency:             {median_latency:.2f}s")
    print(f"P95 Latency:                {p95_latency:.2f}s")
    print("-" * 30)
    print(f"System Throughput:          {global_tps:.2f} tokens/sec")
    print(f"Avg Model Generation Speed: {avg_model_speed:.2f} tokens/sec")
    print("="*50)
    
    # Per Agent Breakdown (simplified)
    # We don't have agent IDs in metrics directly here without more complex patching,
    # but we can show distribution
    print("\nRequest Distribution:")
    print(f"Min Duration: {min(durations):.2f}s")
    print(f"Max Duration: {max(durations):.2f}s")


import argparse

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    parser = argparse.ArgumentParser(description="Benchmark Gemma model")
    parser.add_argument("--model", type=str, default="gemma3:270m", help="Model to benchmark")
    args = parser.parse_args()
    
    asyncio.run(benchmark(args.model))

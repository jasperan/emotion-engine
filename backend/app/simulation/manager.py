"""Simulation Manager - manages multiple concurrent runs"""
import asyncio
from typing import Any, Callable
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.simulation.engine import SimulationEngine, SimulationState
from app.models.scenario import Scenario
from app.models.run import Run, RunStatus


class SimulationManager:
    """
    Manages multiple simulation runs across scenarios.
    Provides high-level API for run lifecycle management.
    """
    
    _instance: "SimulationManager | None" = None
    
    def __init__(self):
        # Active simulation engines by run_id
        self._engines: dict[str, SimulationEngine] = {}
        
        # WebSocket event handlers by run_id
        self._event_handlers: dict[str, list[Callable[[str, dict[str, Any]], None]]] = {}
        
        # Background tasks
        self._tasks: dict[str, asyncio.Task] = {}
    
    @classmethod
    def get_instance(cls) -> "SimulationManager":
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def create_run(
        self,
        db: AsyncSession,
        scenario_id: str,
        seed: int | None = None,
        max_steps: int | None = None,
    ) -> Run:
        """Create a new run for a scenario"""
        # Get scenario
        scenario = await db.get(Scenario, scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        
        # Create run record
        run = Run(
            scenario_id=scenario_id,
            seed=seed,
            max_steps=max_steps or scenario.config.get("max_steps", 100),
            status=RunStatus.PENDING,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        
        return run
    
    async def start_run(
        self,
        db: AsyncSession,
        run_id: str,
    ) -> SimulationEngine:
        """Start a simulation run"""
        # Get run and scenario
        run = await db.get(Run, run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")
        
        scenario = await db.get(Scenario, run.scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {run.scenario_id} not found")
        
        # Create engine
        engine = SimulationEngine(
            run_id=run_id,
            db_session=db,
            on_event=lambda t, d: self._dispatch_event(run_id, t, d),
        )
        
        # Build config from scenario
        config = {
            "config": scenario.config,
            "agent_templates": scenario.agent_templates,
            "seed": run.seed,
        }
        
        # Initialize engine
        await engine.initialize(config)
        
        self._engines[run_id] = engine
        
        # Start in background
        task = asyncio.create_task(engine.start())
        self._tasks[run_id] = task
        
        return engine
    
    async def pause_run(self, run_id: str) -> None:
        """Pause a running simulation"""
        engine = self._engines.get(run_id)
        if engine:
            await engine.pause()
    
    async def resume_run(self, db: AsyncSession, run_id: str) -> None:
        """Resume a paused simulation"""
        engine = self._engines.get(run_id)
        if engine:
            task = asyncio.create_task(engine.resume())
            self._tasks[run_id] = task
    
    async def stop_run(self, run_id: str) -> None:
        """Stop a simulation"""
        engine = self._engines.get(run_id)
        if engine:
            await engine.stop()
            
        # Cancel background task
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
    
    async def step_run(self, run_id: str) -> None:
        """Execute single step of a paused simulation"""
        engine = self._engines.get(run_id)
        if engine:
            await engine.step_once()
    
    def get_engine(self, run_id: str) -> SimulationEngine | None:
        """Get engine for a run"""
        return self._engines.get(run_id)
    
    def get_run_status(self, run_id: str) -> dict[str, Any]:
        """Get current status of a run"""
        engine = self._engines.get(run_id)
        if not engine:
            return {"status": "not_found"}
        
        return {
            "status": engine.state.value,
            "current_step": engine.current_step,
            "max_steps": engine.max_steps,
            "agent_count": len(engine.agents),
            "world_state": engine.world_state,
        }
    
    def subscribe(
        self,
        run_id: str,
        handler: Callable[[str, dict[str, Any]], None],
    ) -> None:
        """Subscribe to events for a run"""
        if run_id not in self._event_handlers:
            self._event_handlers[run_id] = []
        self._event_handlers[run_id].append(handler)
    
    def unsubscribe(
        self,
        run_id: str,
        handler: Callable[[str, dict[str, Any]], None],
    ) -> None:
        """Unsubscribe from events for a run"""
        if run_id in self._event_handlers:
            try:
                self._event_handlers[run_id].remove(handler)
            except ValueError:
                pass
    
    def _dispatch_event(
        self,
        run_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Dispatch event to all subscribers"""
        handlers = self._event_handlers.get(run_id, [])
        for handler in handlers:
            try:
                handler(event_type, data)
            except Exception:
                pass  # Don't let handler errors break the simulation
    
    def cleanup_run(self, run_id: str) -> None:
        """Clean up resources for a completed run"""
        self._engines.pop(run_id, None)
        self._event_handlers.pop(run_id, None)
        task = self._tasks.pop(run_id, None)
        if task and not task.done():
            task.cancel()


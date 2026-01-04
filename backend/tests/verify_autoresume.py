import asyncio
import sys
import os
from sqlalchemy.future import select
from app.models.run import Run, RunStatus
from app.core.database import async_session_maker as AsyncSessionLocal, init_db
from app.simulation.manager import SimulationManager

from app.models.scenario import Scenario

async def test_autoresume():
    print("Initializing DB...")
    await init_db()
    
    async with AsyncSessionLocal() as db:
        # 0. Create a dummy scenario
        print("Creating dummy scenario...")
        scenario = Scenario(
            id="test-scenario-1",
            name="Test Scenario",
            description="A test scenario",
            config={
                "locations": {},
                "agents": [],
                "hazards": []
            }
        )
        db.add(scenario)
        try:
            await db.commit()
        except:
            await db.rollback()
            # If exists, ignore
            pass

        # 1. Create a dummy run that is "RUNNING"
        print("Creating dummy interrupted run...")
        run = Run(
            id="test-autoresume-run",
            scenario_id="test-scenario-1",
            status=RunStatus.RUNNING,  # Simulate interruption
            current_step=5,
            max_steps=10
        )
        db.add(run)
        try:
            await db.commit()
        except:
            await db.rollback() 
            # If it exists, updated it
            run = await db.get(Run, "test-autoresume-run")
            run.status = RunStatus.RUNNING
            await db.commit()
            
    # 2. Trigger auto-resume
    print("Triggering auto-resume...")
    async with AsyncSessionLocal() as db:
        manager = SimulationManager.get_instance()
        # Ensure clean state
        manager._engines = {}
        manager._tasks = {}
        
        count = await manager.resume_all_active_runs(db)
        print(f"Resumed {count} runs")
        
        # 3. Verify
        if count > 0 and "test-autoresume-run" in manager._engines:
            print("SUCCESS: Run was resumed and engine created")
            # Cleanup
            engine = manager._engines["test-autoresume-run"]
            if "test-autoresume-run" in manager._tasks:
                manager._tasks["test-autoresume-run"].cancel()
        else:
            print("FAILURE: Run was not resumed")

if __name__ == "__main__":
    asyncio.run(test_autoresume())

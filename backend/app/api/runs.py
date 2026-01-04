"""Run API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.run import Run
from app.models.agent import AgentModel
from app.models.step import Step
from app.models.message import Message
from app.schemas.run import (
    RunCreate,
    RunResponse,
    RunControl,
    StepResponse,
    MessageResponse,
)
from app.simulation import SimulationManager

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("/", response_model=RunResponse)
async def create_run(
    data: RunCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new run for a scenario"""
    manager = SimulationManager.get_instance()
    
    try:
        run = await manager.create_run(
            db=db,
            scenario_id=data.scenario_id,
            seed=data.seed,
            max_steps=data.max_steps,
        )
        return run
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/", response_model=list[RunResponse])
async def list_runs(
    scenario_id: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List runs, optionally filtered by scenario"""
    query = select(Run).order_by(Run.created_at.desc())
    
    if scenario_id:
        query = query.where(Run.scenario_id == scenario_id)
    
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific run"""
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/{run_id}/control")
async def control_run(
    run_id: str,
    control: RunControl,
    db: AsyncSession = Depends(get_db),
):
    """Control a run (start, pause, resume, stop, step)"""
    manager = SimulationManager.get_instance()
    
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    try:
        if control.action == "start":
            await manager.start_run(db, run_id)
        elif control.action == "pause":
            await manager.pause_run(run_id)
        elif control.action == "resume":
            await manager.resume_run(db, run_id)
        elif control.action == "stop":
            await manager.stop_run(run_id)
        elif control.action == "step":
            await manager.step_run(run_id)
        
        return {"status": "ok", "action": control.action, "run_id": run_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{run_id}/status")
async def get_run_status(run_id: str):
    """Get current status of a run"""
    manager = SimulationManager.get_instance()
    return manager.get_run_status(run_id)


@router.get("/{run_id}/agents")
async def get_run_agents(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all agents for a run"""
    result = await db.execute(
        select(AgentModel).where(AgentModel.run_id == run_id)
    )
    agents = result.scalars().all()
    
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "role": agent.role,
            "model_id": agent.model_id,
            "provider": agent.provider,
            "persona": agent.persona,
            "dynamic_state": agent.dynamic_state,
            "is_active": agent.is_active,
        }
        for agent in agents
    ]


@router.get("/{run_id}/steps", response_model=list[StepResponse])
async def get_run_steps(
    run_id: str,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get steps for a run"""
    result = await db.execute(
        select(Step)
        .where(Step.run_id == run_id)
        .order_by(Step.step_index)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{run_id}/messages", response_model=list[MessageResponse])
async def get_run_messages(
    run_id: str,
    agent_id: str | None = None,
    skip: int = 0,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
):
    """Get messages for a run, optionally filtered by agent"""
    query = select(Message).where(Message.run_id == run_id)
    
    if agent_id:
        query = query.where(
            (Message.from_agent_id == agent_id) | (Message.to_target == agent_id)
        )
    
    result = await db.execute(
        query.order_by(Message.step_index, Message.timestamp)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.delete("/{run_id}")
async def delete_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a run"""
    # Stop if running
    manager = SimulationManager.get_instance()
    await manager.stop_run(run_id)
    manager.cleanup_run(run_id)
    
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    await db.delete(run)
    await db.commit()
    
    return {"status": "deleted", "id": run_id}


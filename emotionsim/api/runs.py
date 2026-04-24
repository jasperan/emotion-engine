"""Run API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from emotionsim.core.database import get_db
from emotionsim.models.run import Run
from emotionsim.models.agent import AgentModel
from emotionsim.models.step import Step
from emotionsim.models.message import Message
from emotionsim.schemas.run import (
    RunCreate,
    RunResponse,
    RunControl,
    StepResponse,
    MessageResponse,
)
from emotionsim.schemas.agent import AgentPlanStatus
from emotionsim.simulation import SimulationManager

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
            llm_backend=data.llm_backend,
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

    # Check for live engine to get cognitive data from in-memory agents
    manager = SimulationManager.get_instance()
    engine = manager.get_engine(run_id)
    live_agents = engine.agents if engine else {}

    agent_list = []
    for agent in agents:
        agent_data = {
            "id": agent.id,
            "name": agent.name,
            "role": agent.role,
            "model_id": agent.model_id,
            "provider": agent.provider,
            "persona": agent.persona,
            "dynamic_state": agent.dynamic_state,
            "is_active": agent.is_active,
            "current_plan": None,
            "last_reasoning": None,
        }

        # Try live agent first (most up-to-date)
        live_agent = live_agents.get(agent.id)
        if live_agent:
            # Extract plan from live agent's intent memory
            if hasattr(live_agent, 'agent_memory') and hasattr(live_agent.agent_memory, 'intent'):
                intent = live_agent.agent_memory.intent
                if intent.current_plan:
                    plan = intent.current_plan
                    current_step_desc = (
                        plan.steps[plan.current_step]
                        if plan.current_step < len(plan.steps)
                        else "Plan complete"
                    )
                    agent_data["current_plan"] = AgentPlanStatus(
                        goal=plan.goal,
                        current_step=current_step_desc,
                        step_progress=f"{plan.current_step + 1}/{len(plan.steps)}",
                        deadline_step=plan.deadline_step,
                    ).model_dump()
            # Extract last reasoning from live agent
            if hasattr(live_agent, 'last_reasoning') and live_agent.last_reasoning:
                agent_data["last_reasoning"] = live_agent.last_reasoning
        else:
            # Fall back to DB memory_snapshot for intent data
            snapshot = agent.memory_snapshot or {}
            intent_data = snapshot.get("intent")
            if intent_data:
                plan_data = intent_data.get("current_plan")
                if plan_data:
                    steps = plan_data.get("steps", [])
                    current_step_idx = plan_data.get("current_step", 0)
                    current_step_desc = (
                        steps[current_step_idx]
                        if current_step_idx < len(steps)
                        else "Plan complete"
                    )
                    agent_data["current_plan"] = AgentPlanStatus(
                        goal=plan_data.get("goal", ""),
                        current_step=current_step_desc,
                        step_progress=f"{current_step_idx + 1}/{len(steps)}",
                        deadline_step=plan_data.get("deadline_step"),
                    ).model_dump()

        agent_list.append(agent_data)

    return agent_list


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

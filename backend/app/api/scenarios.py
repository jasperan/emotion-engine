"""Scenario API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.scenario import Scenario
from app.schemas.scenario import ScenarioCreate, ScenarioUpdate, ScenarioResponse

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.post("/", response_model=ScenarioResponse)
async def create_scenario(
    data: ScenarioCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new scenario"""
    scenario = Scenario(
        name=data.name,
        description=data.description,
        config=data.config.model_dump(),
        agent_templates=[t.model_dump() for t in data.agent_templates],
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    
    return scenario


@router.get("/", response_model=list[ScenarioResponse])
async def list_scenarios(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List all scenarios"""
    result = await db.execute(
        select(Scenario)
        .order_by(Scenario.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific scenario"""
    scenario = await db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@router.put("/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    scenario_id: str,
    data: ScenarioUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a scenario"""
    scenario = await db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    if data.name is not None:
        scenario.name = data.name
    if data.description is not None:
        scenario.description = data.description
    if data.config is not None:
        scenario.config = data.config.model_dump()
    if data.agent_templates is not None:
        scenario.agent_templates = [t.model_dump() for t in data.agent_templates]
    
    await db.commit()
    await db.refresh(scenario)
    
    return scenario


@router.delete("/{scenario_id}")
async def delete_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a scenario"""
    scenario = await db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    await db.delete(scenario)
    await db.commit()
    
    return {"status": "deleted", "id": scenario_id}


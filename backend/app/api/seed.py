"""API endpoint to seed the database with example scenarios"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.scenario import Scenario
from app.scenarios import create_rising_flood_scenario

router = APIRouter(prefix="/seed", tags=["seed"])


@router.post("/rising-flood")
async def seed_rising_flood(db: AsyncSession = Depends(get_db)):
    """Seed the database with the Rising Flood example scenario"""
    
    # Check if it already exists
    result = await db.execute(
        select(Scenario).where(Scenario.name == "Rising Flood")
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        return {
            "status": "exists",
            "message": "Rising Flood scenario already exists",
            "id": existing.id,
        }
    
    # Create the scenario
    scenario_data = create_rising_flood_scenario()
    
    scenario = Scenario(
        name=scenario_data.name,
        description=scenario_data.description,
        config=scenario_data.config.model_dump(),
        agent_templates=[t.model_dump() for t in scenario_data.agent_templates],
    )
    
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    
    return {
        "status": "created",
        "message": "Rising Flood scenario created successfully",
        "id": scenario.id,
    }


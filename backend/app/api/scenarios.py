"""Scenario API endpoints"""
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.scenario import Scenario
from app.schemas.scenario import ScenarioCreate, ScenarioUpdate, ScenarioResponse
from app.scenarios.generator import ScenarioGenerator
from app.scenarios.storage import (
    save_scenario,
    load_scenario,
    list_scenarios,
    delete_scenario as delete_scenario_file,
    dict_to_scenario,
    SCENARIOS_DIR,
)

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


class GenerateRequest(BaseModel):
    """Request body for scenario generation"""
    prompt: str = Field(..., min_length=3, description="Scenario description")
    persona_count: int = Field(6, ge=2, le=12, description="Number of personas")
    archetypes: list[str] | None = Field(None, description="Optional persona types")
    save_to_file: bool = Field(True, description="Save to JSON file")


class GenerateResponse(BaseModel):
    """Response from scenario generation"""
    scenario: dict[str, Any]
    filepath: str | None = None
    message: str


class ScenarioFileResponse(BaseModel):
    """Response for listing scenario files"""
    filename: str
    filepath: str
    name: str
    description: str
    generated_at: str | None
    persona_count: int


@router.post("/generate", response_model=GenerateResponse)
async def generate_scenario(
    request: GenerateRequest,
):
    """
    Generate a new scenario using AI based on a natural language prompt.
    
    Examples:
    - "earthquake in Tokyo with rescue workers and civilians"
    - "zombie outbreak in a shopping mall"
    - "hostage negotiation at a bank"
    """
    generator = ScenarioGenerator()
    
    try:
        scenario = await generator.generate(
            prompt=request.prompt,
            persona_count=request.persona_count,
            archetypes=request.archetypes,
        )
        
        filepath = None
        if request.save_to_file:
            filepath = save_scenario(scenario)
            filepath = str(filepath)
        
        return GenerateResponse(
            scenario={
                "name": scenario.name,
                "description": scenario.description,
                "config": scenario.config.model_dump(),
                "agent_templates": [t.model_dump() for t in scenario.agent_templates],
            },
            filepath=filepath,
            message=f"Successfully generated scenario: {scenario.name}",
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.get("/files", response_model=list[ScenarioFileResponse])
async def list_scenario_files():
    """List all generated scenario JSON files"""
    scenarios = list_scenarios()
    return [
        ScenarioFileResponse(
            filename=s["filename"],
            filepath=s["filepath"],
            name=s["name"],
            description=s["description"],
            generated_at=s.get("generated_at"),
            persona_count=s["persona_count"],
        )
        for s in scenarios
    ]


@router.get("/files/{filename}")
async def get_scenario_file(filename: str):
    """Get a specific scenario file by filename"""
    filepath = SCENARIOS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Scenario file not found")
    
    scenario = load_scenario(filepath)
    return {
        "name": scenario.name,
        "description": scenario.description,
        "config": scenario.config.model_dump(),
        "agent_templates": [t.model_dump() for t in scenario.agent_templates],
    }


@router.delete("/files/{filename}")
async def delete_scenario_file_endpoint(filename: str):
    """Delete a scenario file"""
    filepath = SCENARIOS_DIR / filename
    if delete_scenario_file(filepath):
        return {"status": "deleted", "filename": filename}
    raise HTTPException(status_code=404, detail="Scenario file not found")


@router.post("/files/{filename}/import", response_model=ScenarioResponse)
async def import_scenario_file(
    filename: str,
    db: AsyncSession = Depends(get_db),
):
    """Import a scenario file into the database"""
    filepath = SCENARIOS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Scenario file not found")
    
    scenario_data = load_scenario(filepath)
    
    # Create database entry
    scenario = Scenario(
        name=scenario_data.name,
        description=scenario_data.description,
        config=scenario_data.config.model_dump(),
        agent_templates=[t.model_dump() for t in scenario_data.agent_templates],
    )
    db.add(scenario)
    await db.commit()
    await db.refresh(scenario)
    
    return scenario


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


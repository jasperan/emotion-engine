"""JSON storage utilities for scenarios"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from app.schemas.scenario import ScenarioCreate, WorldConfig
from app.schemas.agent import AgentConfig
from app.schemas.persona import Persona


# Default directory for generated scenarios
SCENARIOS_DIR = Path(__file__).parent.parent.parent / "scenarios_generated"


def ensure_scenarios_dir() -> Path:
    """Ensure the scenarios directory exists"""
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)
    return SCENARIOS_DIR


def scenario_to_dict(scenario: ScenarioCreate) -> dict[str, Any]:
    """Convert ScenarioCreate to a serializable dict"""
    return {
        "name": scenario.name,
        "description": scenario.description,
        "config": scenario.config.model_dump(),
        "agent_templates": [t.model_dump() for t in scenario.agent_templates],
        "generated_at": datetime.utcnow().isoformat(),
    }


def dict_to_scenario(data: dict[str, Any]) -> ScenarioCreate:
    """Convert dict back to ScenarioCreate"""
    # Parse world config
    config_data = data["config"]
    world_config = WorldConfig(
        name=config_data["name"],
        description=config_data.get("description", ""),
        initial_state=config_data.get("initial_state", {}),
        dynamics=config_data.get("dynamics", {}),
        max_steps=config_data.get("max_steps", 50),
        tick_delay=config_data.get("tick_delay", 1.0),
    )
    
    # Parse agent templates
    agent_templates = []
    for t_data in data["agent_templates"]:
        persona = None
        if t_data.get("persona"):
            persona = Persona(**t_data["persona"])
        
        agent_templates.append(AgentConfig(
            name=t_data["name"],
            role=t_data["role"],
            model_id=t_data.get("model_id", "qwen2.5:7b"),
            provider=t_data.get("provider", "ollama"),
            persona=persona,
            goals=t_data.get("goals", []),
            tools=t_data.get("tools", []),
            initial_state=t_data.get("initial_state", {}),
        ))
    
    return ScenarioCreate(
        name=data["name"],
        description=data["description"],
        config=world_config,
        agent_templates=agent_templates,
    )


def generate_filename(name: str) -> str:
    """Generate a safe filename from scenario name"""
    # Convert to lowercase and replace spaces with underscores
    safe_name = name.lower().replace(" ", "_")
    # Remove special characters
    safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
    # Add timestamp for uniqueness
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"{safe_name}_{timestamp}.json"


def save_scenario(
    scenario: ScenarioCreate,
    filename: str | None = None,
    directory: Path | None = None,
) -> Path:
    """
    Save a scenario to a JSON file.
    
    Args:
        scenario: The scenario to save
        filename: Optional filename (auto-generated if not provided)
        directory: Optional directory (uses default if not provided)
        
    Returns:
        Path to the saved file
    """
    target_dir = directory or ensure_scenarios_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    
    if filename is None:
        filename = generate_filename(scenario.name)
    
    if not filename.endswith(".json"):
        filename += ".json"
    
    filepath = target_dir / filename
    
    data = scenario_to_dict(scenario)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return filepath


def load_scenario(filepath: str | Path) -> ScenarioCreate:
    """
    Load a scenario from a JSON file.
    
    Args:
        filepath: Path to the JSON file
        
    Returns:
        ScenarioCreate object
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return dict_to_scenario(data)


def list_scenarios(directory: Path | None = None) -> list[dict[str, Any]]:
    """
    List all scenarios in the directory.
    
    Args:
        directory: Optional directory (uses default if not provided)
        
    Returns:
        List of dicts with scenario metadata
    """
    target_dir = directory or SCENARIOS_DIR
    
    if not target_dir.exists():
        return []
    
    scenarios = []
    for filepath in target_dir.glob("*.json"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            scenarios.append({
                "filename": filepath.name,
                "filepath": str(filepath),
                "name": data.get("name", "Unknown"),
                "description": data.get("description", ""),
                "generated_at": data.get("generated_at"),
                "persona_count": len([
                    t for t in data.get("agent_templates", [])
                    if t.get("role") == "human"
                ]),
            })
        except (json.JSONDecodeError, KeyError):
            # Skip invalid files
            continue
    
    # Sort by generation time (newest first)
    scenarios.sort(key=lambda x: x.get("generated_at", ""), reverse=True)
    return scenarios


def delete_scenario(filepath: str | Path) -> bool:
    """
    Delete a scenario file.
    
    Args:
        filepath: Path to the JSON file
        
    Returns:
        True if deleted, False if file didn't exist
    """
    path = Path(filepath)
    if path.exists():
        path.unlink()
        return True
    return False


def update_scenario(
    filepath: str | Path,
    updates: dict[str, Any],
) -> ScenarioCreate:
    """
    Update a scenario file with partial updates.
    
    Args:
        filepath: Path to the JSON file
        updates: Dict of fields to update
        
    Returns:
        Updated ScenarioCreate object
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Apply updates
    for key, value in updates.items():
        if key in data:
            data[key] = value
    
    # Update timestamp
    data["updated_at"] = datetime.utcnow().isoformat()
    
    # Save back
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return dict_to_scenario(data)


def load_generated_scenarios() -> list[dict[str, Any]]:
    """
    Load all generated scenarios from the scenarios_generated directory.
    
    Returns:
        List of dicts with scenario data ready for use in CLI/API
    """
    scenarios = []
    
    if not SCENARIOS_DIR.exists():
        return scenarios
    
    for filepath in sorted(SCENARIOS_DIR.glob("*.json")):
        # Skip .gitkeep and other non-scenario files
        if filepath.name.startswith("."):
            continue
            
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Validate it has required fields
            if "name" not in data or "agent_templates" not in data:
                continue
            
            scenarios.append({
                "filename": filepath.name,
                "filepath": str(filepath),
                "name": data.get("name", "Unknown"),
                "description": data.get("description", ""),
                "generated_at": data.get("generated_at"),
                "agent_count": len(data.get("agent_templates", [])),
                "persona_count": len([
                    t for t in data.get("agent_templates", [])
                    if t.get("role") == "human"
                ]),
                "config": data.get("config", {}),
                "agent_templates": data.get("agent_templates", []),
            })
        except (json.JSONDecodeError, KeyError, OSError):
            # Skip invalid files
            continue
    
    # Sort by generation time (newest first)
    scenarios.sort(key=lambda x: x.get("generated_at", ""), reverse=True)
    return scenarios


"""Generate a new scenario using the ScenarioGenerator"""
import asyncio
import json
from app.scenarios.generator import ScenarioGenerator

async def main():
    """Generate a scenario and save it to a file"""
    generator = ScenarioGenerator()
    
    # Generate the "Wildfire Evacuation" scenario
    prompt = "A wildfire is rapidly approaching a small town. The agents must evacuate the town, and deal with challenges like blocked roads, communication failures, and helping vulnerable residents."
    scenario = await generator.generate(prompt, persona_count=50)
    
    # Save the scenario to a file
    file_path = "scenarios_generated/wildfire_evacuation.json"
    with open(file_path, "w") as f:
        json.dump(scenario.model_dump(), f, indent=2)
        
    print(f"Scenario saved to {file_path}")

if __name__ == "__main__":
    asyncio.run(main())

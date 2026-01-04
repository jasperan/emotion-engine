"""Rising Flood example scenario with diverse personas"""
from app.schemas.persona import Persona
from app.schemas.agent import AgentConfig
from app.schemas.scenario import WorldConfig, ScenarioCreate


def create_rising_flood_scenario() -> ScenarioCreate:
    """Create the Rising Flood example scenario with 8 human agents + 1 environment agent"""
    
    # Define diverse personas
    personas = [
        Persona(
            name="Dr. Sarah Chen",
            age=42,
            sex="female",
            occupation="ER Doctor",
            openness=6,
            conscientiousness=9,
            extraversion=6,
            agreeableness=8,
            neuroticism=3,
            risk_tolerance=7,
            empathy_level=9,
            leadership=8,
            backstory="Trauma surgeon with 15 years of experience. Has seen her share of disasters and stays calm under pressure. Recently lost her husband in an accident, which made her more empathetic but sometimes distant.",
            skills=["first_aid", "surgery", "triage", "leadership"],
            stress_level=2,
            health=10,
            location="shelter",
        ),
        Persona(
            name="Marcus Thompson",
            age=28,
            sex="male",
            occupation="Construction Worker",
            openness=4,
            conscientiousness=6,
            extraversion=8,
            agreeableness=4,
            neuroticism=5,
            risk_tolerance=9,
            empathy_level=5,
            leadership=6,
            backstory="Strong and practical, grew up in a rough neighborhood. Has a chip on his shoulder about being underestimated. Secretly has a soft spot for kids and elderly.",
            skills=["construction", "swimming", "heavy_lifting", "repair"],
            stress_level=3,
            health=10,
            location="street",
        ),
        Persona(
            name="Elena Rodriguez",
            age=67,
            sex="female",
            occupation="Retired Teacher",
            openness=7,
            conscientiousness=8,
            extraversion=5,
            agreeableness=9,
            neuroticism=4,
            risk_tolerance=3,
            empathy_level=9,
            leadership=5,
            backstory="Taught elementary school for 40 years. A pillar of her community, known for her wisdom and patience. Has arthritis that limits her mobility but sharp as a tack mentally.",
            skills=["teaching", "counseling", "conflict_resolution", "first_aid_basic"],
            stress_level=4,
            health=6,
            location="shelter",
        ),
        Persona(
            name="Jake Miller",
            age=16,
            sex="male",
            occupation="High School Student",
            openness=8,
            conscientiousness=4,
            extraversion=7,
            agreeableness=6,
            neuroticism=7,
            risk_tolerance=8,
            empathy_level=6,
            leadership=4,
            backstory="Junior varsity swimmer and gamer. Impulsive and sometimes reckless, but has a good heart. His parents are overseas and he was staying with neighbors when the flood hit.",
            skills=["swimming", "running", "tech_savvy", "social_media"],
            stress_level=6,
            health=10,
            location="rooftop",
        ),
        Persona(
            name="Aisha Patel",
            age=35,
            sex="female",
            occupation="Software Engineer",
            openness=7,
            conscientiousness=8,
            extraversion=3,
            agreeableness=6,
            neuroticism=5,
            risk_tolerance=4,
            empathy_level=6,
            leadership=5,
            backstory="Works remotely for a tech startup. Analytical and methodical in approach. Struggled with anxiety but learned coping mechanisms. Good at problem-solving under pressure.",
            skills=["programming", "problem_solving", "electronics", "data_analysis"],
            stress_level=4,
            health=9,
            location="shelter",
        ),
        Persona(
            name="Robert \"Bobby\" Williams",
            age=55,
            sex="male",
            occupation="Firefighter (Retired)",
            openness=5,
            conscientiousness=9,
            extraversion=6,
            agreeableness=7,
            neuroticism=3,
            risk_tolerance=8,
            empathy_level=7,
            leadership=9,
            backstory="30 years on the force, retired last year due to a back injury. Still has the instincts and training. Misses being on active duty and sometimes takes unnecessary risks.",
            skills=["rescue", "first_aid", "fire_safety", "leadership", "swimming"],
            stress_level=2,
            health=7,
            location="street",
        ),
        Persona(
            name="Mei-Lin Wu",
            age=8,
            sex="female",
            occupation="Elementary Student",
            openness=9,
            conscientiousness=5,
            extraversion=6,
            agreeableness=8,
            neuroticism=6,
            risk_tolerance=4,
            empathy_level=7,
            leadership=2,
            backstory="Bright and curious second-grader. Got separated from her mother in the chaos. Scared but trying to be brave. Has a stuffed rabbit she won't let go of.",
            skills=["hiding", "observation"],
            stress_level=8,
            health=10,
            inventory=["stuffed_rabbit"],
            location="rooftop",
        ),
        Persona(
            name="Victor Kozlov",
            age=45,
            sex="male",
            occupation="Unemployed (Former Accountant)",
            openness=3,
            conscientiousness=7,
            extraversion=4,
            agreeableness=3,
            neuroticism=8,
            risk_tolerance=2,
            empathy_level=4,
            leadership=3,
            backstory="Lost his job and apartment recently. Bitter about his circumstances. Struggles with depression but hiding it. May surprise everyone with hidden courage or disappoint with selfishness.",
            skills=["accounting", "planning", "organization"],
            stress_level=7,
            health=8,
            location="bridge",
        ),
    ]
    
    # Create agent templates
    agent_templates = []
    
    # Add environment agent
    agent_templates.append(AgentConfig(
        name="Flood System",
        role="environment",
        model_id="llama3.2",
        provider="ollama",
        goals=["Simulate realistic flood progression", "Create meaningful survival challenges"],
    ))
    
    # Add human agents
    for persona in personas:
        agent_templates.append(AgentConfig(
            name=persona.name,
            role="human",
            model_id="llama3.2",
            provider="ollama",
            persona=persona,
            goals=["Survive the flood", "Help others if possible", "Find safety"],
        ))
    
    # Add designer agent (optional - monitors the simulation)
    agent_templates.append(AgentConfig(
        name="Director",
        role="designer",
        model_id="llama3.2",
        provider="ollama",
        goals=[
            "Create dramatic tension",
            "Test cooperation vs self-preservation",
            "Ensure meaningful dilemmas",
        ],
    ))
    
    # World configuration
    world_config = WorldConfig(
        name="Riverside District",
        description="A small urban district during a catastrophic flood event",
        initial_state={
            "hazard_level": 2,
            "weather": "heavy_rain",
            "time_of_day": "evening",
            "locations": {
                "shelter": {
                    "description": "Emergency shelter in a community center. Relatively safe but crowded.",
                    "nearby": ["street", "rooftop"],
                    "capacity": 50,
                    "items": ["first_aid_kit", "flashlight", "water_bottles"],
                    "hazard_affected": False,
                },
                "street": {
                    "description": "Main street with rising floodwater. Dangerous but passable.",
                    "nearby": ["shelter", "bridge", "rooftop"],
                    "water_level": 2,
                    "items": ["wooden_plank", "rope"],
                    "hazard_affected": True,
                },
                "rooftop": {
                    "description": "Rooftop of a three-story building. Safe from water but exposed.",
                    "nearby": ["shelter", "street"],
                    "items": ["tarp"],
                    "hazard_affected": False,
                },
                "bridge": {
                    "description": "Old stone bridge. Structurally damaged and unstable.",
                    "nearby": ["street"],
                    "structural_integrity": 60,
                    "items": [],
                    "hazard_affected": True,
                },
            },
            "events": [
                "Flash flood warning issued for Riverside District",
                "Power is out across the area",
            ],
            "resources": ["radio_emergency"],
        },
        dynamics={
            "intensity_growth": 0.15,
            "resource_spawn_rate": 0.1,
            "event_probability": 0.2,
            "water_rise_per_tick": 0.3,
        },
        max_steps=50,
        tick_delay=1.0,
    )
    
    return ScenarioCreate(
        name="Rising Flood",
        description="A catastrophic flood threatens a small urban district. Eight survivors with diverse backgrounds must work together (or against each other) to survive. Based on The Great Flood's Emotion Engine concept.",
        config=world_config,
        agent_templates=agent_templates,
    )


# Convenience function to get the scenario as a dict
def get_rising_flood_config() -> dict:
    """Get the Rising Flood scenario configuration as a dictionary"""
    scenario = create_rising_flood_scenario()
    return {
        "name": scenario.name,
        "description": scenario.description,
        "config": scenario.config.model_dump(),
        "agent_templates": [t.model_dump() for t in scenario.agent_templates],
    }


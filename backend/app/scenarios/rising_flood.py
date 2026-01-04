"""Rising Flood example scenario with diverse personas - Enhanced for conversation system"""
import random
from app.schemas.persona import Persona
from app.schemas.agent import AgentConfig
from app.schemas.scenario import WorldConfig, ScenarioCreate


def _generate_additional_personas(count: int, seed: int = 42) -> list[Persona]:
    """Generate additional diverse personas for the Rising Flood scenario"""
    random.seed(seed)
    
    first_names_male = ["James", "Michael", "David", "Daniel", "Christopher", "Matthew", "Andrew", "Joshua", "John", "William", "Ryan", "Joseph", "Anthony", "Mark", "Thomas", "Steven", "Kevin", "Brian", "Jason", "Justin"]
    first_names_female = ["Sarah", "Emily", "Jessica", "Ashley", "Amanda", "Melissa", "Nicole", "Michelle", "Laura", "Kimberly", "Amy", "Angela", "Lisa", "Jennifer", "Stephanie", "Rebecca", "Elizabeth", "Samantha", "Rachel", "Lauren"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee"]
    
    occupations = [
        "Nurse", "Paramedic", "Police Officer", "Teacher", "Engineer", "Mechanic", 
        "Chef", "Retail Worker", "Delivery Driver", "Security Guard", "Janitor",
        "Electrician", "Plumber", "Carpenter", "Bus Driver", "Taxi Driver",
        "Librarian", "Social Worker", "Counselor", "Pharmacist", "Dentist",
        "Veterinarian", "Architect", "Lawyer", "Accountant", "Banker",
        "Real Estate Agent", "Insurance Agent", "Sales Representative", "Manager",
        "Waiter", "Bartender", "Barista", "Cashier", "Receptionist", "Secretary"
    ]
    
    skills_sets = [
        ["first_aid", "communication"],
        ["swimming", "physical_strength"],
        ["navigation", "problem_solving"],
        ["cooking", "organization"],
        ["mechanical_repair", "tools"],
        ["electronics", "troubleshooting"],
        ["leadership", "decision_making"],
        ["calm_under_pressure", "empathy"],
        ["physical_fitness", "endurance"],
        ["communication", "conflict_resolution"],
    ]
    
    locations = ["shelter", "street", "rooftop", "bridge", "flooded_house", "medical_station", "safe_hill"]
    
    personas = []
    used_names = set()
    
    for i in range(count):
        # Generate diverse attributes
        sex = random.choice(["male", "female", "non-binary"])
        age = random.randint(18, 75)
        
        # Generate unique name
        if sex == "male":
            first_name = random.choice(first_names_male)
        elif sex == "female":
            first_name = random.choice(first_names_female)
        else:
            first_name = random.choice(first_names_male + first_names_female)
        
        last_name = random.choice(last_names)
        full_name = f"{first_name} {last_name}"
        
        # Ensure unique name
        counter = 1
        while full_name in used_names:
            full_name = f"{first_name} {last_name} {counter}"
            counter += 1
        used_names.add(full_name)
        
        occupation = random.choice(occupations)
        skills = random.choice(skills_sets)
        location = random.choice(locations)
        
        # Generate personality traits with some variation
        openness = random.randint(3, 9)
        conscientiousness = random.randint(4, 10)
        extraversion = random.randint(2, 9)
        agreeableness = random.randint(3, 10)
        neuroticism = random.randint(2, 8)
        risk_tolerance = random.randint(2, 9)
        empathy_level = random.randint(4, 10)
        leadership = random.randint(2, 9)
        
        # Generate backstory
        backstory_options = [
            f"Works as a {occupation.lower()}. {random.choice(['Recently moved to the area.', 'Lived here all their life.', 'Visiting family when the flood hit.'])}",
            f"{occupation.lower()} with {random.randint(1, 20)} years of experience. {random.choice(['Known for being reliable.', 'Sometimes struggles with stress.', 'Always willing to help others.'])}",
            f"Recently {random.choice(['started a new job', 'retired', 'graduated from school'])}. {random.choice(['Looking forward to the future.', 'Uncertain about what comes next.', 'Trying to make the best of things.'])}",
        ]
        backstory = random.choice(backstory_options)
        
        # Generate initial state
        stress_level = random.randint(2, 7)
        health = random.randint(6, 10)
        
        persona = Persona(
            name=full_name,
            age=age,
            sex=sex,
            occupation=occupation,
            openness=openness,
            conscientiousness=conscientiousness,
            extraversion=extraversion,
            agreeableness=agreeableness,
            neuroticism=neuroticism,
            risk_tolerance=risk_tolerance,
            empathy_level=empathy_level,
            leadership=leadership,
            backstory=backstory,
            skills=skills,
            stress_level=stress_level,
            health=health,
            location=location,
        )
        personas.append(persona)
    
    return personas


def create_rising_flood_scenario() -> ScenarioCreate:
    """Create the Rising Flood example scenario with 50 human agents + 1 environment agent"""
    
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
    
    # Generate additional personas to reach 50 total
    additional_count = 50 - len(personas)
    if additional_count > 0:
        additional_personas = _generate_additional_personas(additional_count, seed=42)
        personas.extend(additional_personas)
    
    # Create agent templates
    agent_templates = []
    
    # Add environment agent
    agent_templates.append(AgentConfig(
        name="Flood System",
        role="environment",
        model_id="qwen2.5:7b",
        provider="ollama",
        goals=[
            "Simulate realistic flood progression",
            "Create meaningful survival challenges",
            "Generate events that force cooperation",
        ],
    ))
    
    # Add human agents with enhanced goals for conversation system
    for persona in personas:
        agent_templates.append(AgentConfig(
            name=persona.name,
            role="human",
            model_id="qwen2.5:7b",
            provider="ollama",
            persona=persona,
            goals=[
                "Save as many lives as possible including yourself",
                "Help others reach safety",
                "Coordinate with others to share resources",
                "Find and rescue anyone in danger",
                "Make it to a safe location",
            ],
        ))
    
    # World configuration - enhanced with more locations for movement
    world_config = WorldConfig(
        name="Riverside District",
        description="A small urban district during a catastrophic flood event. Rising waters threaten multiple locations as survivors must work together to save lives.",
        initial_state={
            "hazard_level": 2,
            "weather": "heavy_rain",
            "time_of_day": "evening",
            "survivors_at_risk": 3,
            "survivors_rescued": 0,
            "locations": {
                "shelter": {
                    "description": "Emergency shelter in a community center. Relatively safe but crowded. Dr. Chen and Elena are organizing supplies.",
                    "nearby": ["street", "rooftop", "medical_station"],
                    "capacity": 50,
                    "current_occupants": 15,
                    "items": ["first_aid_kit", "flashlight", "water_bottles", "blankets", "radio"],
                    "hazard_affected": False,
                    "observations": [
                        "People are scared and looking for leadership",
                        "Supplies are running low",
                        "Someone should check on people at other locations",
                    ],
                },
                "street": {
                    "description": "Main street with rising floodwater. Dangerous but passable for now. Marcus and Bobby are here assessing the situation.",
                    "nearby": ["shelter", "bridge", "rooftop", "flooded_house"],
                    "water_level": 2,
                    "items": ["wooden_plank", "rope", "sandbags"],
                    "hazard_affected": True,
                    "observations": [
                        "Water is rising steadily",
                        "Someone might be trapped in a flooded house",
                        "The bridge looks unstable",
                    ],
                },
                "rooftop": {
                    "description": "Rooftop of a three-story building. Safe from water but exposed to the storm. Jake and Mei-Lin are stranded here.",
                    "nearby": ["shelter", "street"],
                    "items": ["tarp", "rope"],
                    "hazard_affected": False,
                    "observations": [
                        "Can see the whole district from here",
                        "Spotted movement near the bridge",
                        "The child seems scared",
                    ],
                },
                "bridge": {
                    "description": "Old stone bridge. Structurally damaged and unstable. Victor is here, seemingly paralyzed with fear.",
                    "nearby": ["street", "safe_hill"],
                    "structural_integrity": 60,
                    "items": [],
                    "hazard_affected": True,
                    "observations": [
                        "Bridge is creaking ominously",
                        "Could collapse at any moment",
                        "Someone needs to help Victor cross",
                    ],
                },
                "flooded_house": {
                    "description": "A partially flooded house. Someone is calling for help from the second floor.",
                    "nearby": ["street"],
                    "water_level": 4,
                    "items": [],
                    "hazard_affected": True,
                    "observations": [
                        "Elderly person trapped on second floor",
                        "Water still rising",
                        "Need a boat or strong swimmer",
                    ],
                    "trapped_survivor": True,
                },
                "medical_station": {
                    "description": "Makeshift medical station set up near the shelter. Dr. Chen can treat the injured here.",
                    "nearby": ["shelter"],
                    "items": ["medical_supplies", "stretcher", "medication"],
                    "hazard_affected": False,
                    "observations": [
                        "Several people need medical attention",
                        "Supplies are limited",
                    ],
                },
                "safe_hill": {
                    "description": "High ground overlooking the district. Completely safe from flooding. This is the evacuation point.",
                    "nearby": ["bridge"],
                    "items": ["emergency_supplies"],
                    "hazard_affected": False,
                    "observations": [
                        "Rescue helicopters might land here",
                        "Best vantage point to coordinate",
                    ],
                },
            },
            "events": [
                "Flash flood warning issued for Riverside District",
                "Power is out across the area",
                "Someone is calling for help from a flooded house",
                "The old bridge is showing signs of stress",
            ],
            "resources": ["radio_emergency", "rescue_boats_incoming"],
        },
        dynamics={
            "intensity_growth": 0.15,
            "resource_spawn_rate": 0.1,
            "event_probability": 0.2,
            "water_rise_per_tick": 0.3,
            "bridge_deterioration": 0.05,
        },
        max_steps=50,
        tick_delay=1.0,
    )
    
    return ScenarioCreate(
        name="Rising Flood",
        description="A catastrophic flood threatens a small urban district. Fifty survivors with diverse backgrounds must work together to save as many lives as possible. Features multiple locations requiring coordination, trapped survivors to rescue, and a deteriorating bridge. Based on The Great Flood's Emotion Engine concept.",
        config=world_config,
        agent_templates=agent_templates,
    )


def get_rising_flood_config() -> dict:
    """Get the Rising Flood scenario configuration as a dictionary"""
    scenario = create_rising_flood_scenario()
    return {
        "name": scenario.name,
        "description": scenario.description,
        "config": scenario.config.model_dump(),
        "agent_templates": [t.model_dump() for t in scenario.agent_templates],
    }

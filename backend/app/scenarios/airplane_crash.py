"""Airplane Crash Investigation - agents investigate and reach conclusions"""
from app.schemas.persona import Persona
from app.schemas.agent import AgentConfig
from app.schemas.scenario import WorldConfig, ScenarioCreate


def create_airplane_crash_scenario(num_agents: int = 8) -> ScenarioCreate:
    """Create the Airplane Crash Investigation scenario with a specified number of diverse personas"""
    
    # Define diverse personas with different expertise and perspectives
    base_personas = [
        Persona(
            name="Captain James Mitchell",
            age=58,
            sex="male",
            occupation="Retired Air Force Pilot",
            openness=6,
            conscientiousness=9,
            extraversion=7,
            agreeableness=6,
            neuroticism=3,
            risk_tolerance=7,
            empathy_level=7,
            leadership=9,
            backstory="Flew commercial jets for 20 years before retiring. Has extensive knowledge of aircraft systems and emergency procedures. Known for being methodical and authoritative. Lives two blocks from the crash site.",
            skills=["aviation_knowledge", "emergency_procedures", "leadership", "investigation"],
            stress_level=4,
            health=9,
            location="crash_site",
            inventory=["binoculars", "flashlight"],
        ),
        Persona(
            name="Dr. Priya Sharma",
            age=34,
            sex="female",
            occupation="Emergency Room Physician",
            openness=7,
            conscientiousness=9,
            extraversion=5,
            agreeableness=8,
            neuroticism=4,
            risk_tolerance=6,
            empathy_level=9,
            leadership=6,
            backstory="Works at the local hospital. First responder training. Calm under pressure but deeply affected by trauma. Was at home when she heard the crash and rushed to help.",
            skills=["medical_treatment", "triage", "first_aid", "observation"],
            stress_level=5,
            health=10,
            location="crash_site",
            inventory=["medical_bag", "phone"],
        ),
        Persona(
            name="Tommy Rodriguez",
            age=19,
            sex="male",
            occupation="College Student (Aviation Major)",
            openness=9,
            conscientiousness=6,
            extraversion=8,
            agreeableness=7,
            neuroticism=5,
            risk_tolerance=8,
            empathy_level=6,
            leadership=5,
            backstory="Studying to become a pilot. Obsessed with planes and flight data. Was walking his dog when the plane crashed. Saw the approach from a unique angle. Has flight tracking apps on his phone.",
            skills=["aviation_knowledge", "tech_savvy", "observation", "data_analysis"],
            stress_level=6,
            health=10,
            location="hilltop",
            inventory=["phone", "notebook", "pen"],
        ),
        Persona(
            name="Margaret Chen",
            age=72,
            sex="female",
            occupation="Retired School Principal",
            openness=5,
            conscientiousness=8,
            extraversion=6,
            agreeableness=7,
            neuroticism=6,
            risk_tolerance=3,
            empathy_level=8,
            leadership=7,
            backstory="Retired after 40 years in education. Known for being organized and detail-oriented. Lives directly across from the crash site. Saw everything from her kitchen window. Takes meticulous notes.",
            skills=["observation", "organization", "note_taking", "conflict_resolution"],
            stress_level=7,
            health=8,
            location="residential_area",
            inventory=["notebook", "glasses", "phone"],
        ),
        Persona(
            name="Marcus Johnson",
            age=45,
            sex="male",
            occupation="Local Mechanic",
            openness=4,
            conscientiousness=7,
            extraversion=8,
            agreeableness=5,
            neuroticism=4,
            risk_tolerance=8,
            empathy_level=5,
            leadership=6,
            backstory="Owns the auto shop down the street. Practical, hands-on problem solver. Doesn't trust authority figures. Was working on a car when the crash happened. Rushed to help with tools and equipment.",
            skills=["mechanical_knowledge", "tools", "practical_problem_solving", "heavy_lifting"],
            stress_level=4,
            health=10,
            location="crash_site",
            inventory=["toolbox", "flashlight", "crowbar"],
        ),
        Persona(
            name="Lisa Park",
            age=29,
            sex="female",
            occupation="Journalist (Local News)",
            openness=8,
            conscientiousness=6,
            extraversion=7,
            agreeableness=5,
            neuroticism=5,
            risk_tolerance=7,
            empathy_level=5,
            leadership=4,
            backstory="Investigative reporter for the local paper. Always looking for the story. Arrived quickly after hearing police scanners. Has contacts in emergency services. Sometimes puts the story before people's feelings.",
            skills=["investigation", "interviewing", "note_taking", "networking"],
            stress_level=5,
            health=10,
            location="perimeter",
            inventory=["phone", "notebook", "camera"],
        ),
        Persona(
            name="Reverend David Williams",
            age=55,
            sex="male",
            occupation="Community Pastor",
            openness=6,
            conscientiousness=7,
            extraversion=7,
            agreeableness=9,
            neuroticism=4,
            risk_tolerance=5,
            empathy_level=10,
            leadership=7,
            backstory="Pastor of the local church. Known for bringing people together in crisis. Arrived to provide comfort and support. Believes in finding truth through compassion and dialogue.",
            skills=["counseling", "conflict_resolution", "leadership", "community_organizing"],
            stress_level=5,
            health=9,
            location="community_center",
            inventory=["bible", "phone"],
        ),
        Persona(
            name="Alex Kim",
            age=31,
            sex="non-binary",
            occupation="Software Engineer (Remote Worker)",
            openness=8,
            conscientiousness=7,
            extraversion=3,
            agreeableness=6,
            neuroticism=6,
            risk_tolerance=4,
            empathy_level=6,
            leadership=3,
            backstory="Works from home. Analytical and logical. Was on a video call when the crash happened. Has been monitoring social media and news for information. Prefers data over speculation.",
            skills=["data_analysis", "research", "tech_savvy", "critical_thinking"],
            stress_level=6,
            health=10,
            location="residential_area",
            inventory=["laptop", "phone", "tablet"],
        ),
    ]
    
    from app.scenarios.generator import PersonaGenerator
    personas = PersonaGenerator.generate_personas(base_personas, num_agents)
    
    # Create agent templates
    agent_templates = []
    
    # Add environment agent (represents the crash site and ongoing situation)
    agent_templates.append(AgentConfig(
        name="Crash Site Environment",
        role="environment",
        model_id="gemma3",
        provider="ollama",
        goals=[
            "Simulate realistic crash site conditions",
            "Reveal clues gradually as investigation progresses",
            "Create investigation challenges and new discoveries",
        ],
    ))
    
    # Add human agents
    for persona in personas:
        agent_templates.append(AgentConfig(
            name=persona.name,
            role="human",
            model_id="gemma3",
            provider="ollama",
            persona=persona,
            goals=[
                "Save any survivors from the crash",
                "Investigate what happened to the airplane",
                "Share information and observations with others",
                "Help coordinate emergency response",
                "Reach a conclusion about the cause",
            ],
        ))
    
    # World configuration
    world_config = WorldConfig(
        name="Riverside Neighborhood",
        description="A quiet suburban neighborhood where a small passenger plane has just crashed. Residents and first responders are gathering to investigate and help.",
        initial_state={
            "hazard_level": 6,
            "time_of_day": "late_afternoon",
            "temperature": "72°F",
            "city": "Chicago",
            "country": "USA",
            "weather": "clear_skies",
            "emergency_services": "en_route",
            "crash_time": "15_minutes_ago",
            "survivors_found": 0,
            "survivors_total": 3,
            "locations": {
                "crash_site": {
                    "description": "The main crash site. Debris scattered across a 200-yard radius. Small fires burning. Plane appears to be a twin-engine turboprop. Tail section mostly intact, but fuselage is severely damaged.",
                    "nearby": ["hilltop", "residential_area", "perimeter"],
                    "hazard_affected": True,
                    "items": ["wreckage", "emergency_beacon", "fire_extinguisher"],
                    "observations": [
                        "Engine on left wing appears to have failed",
                        "Landing gear was not deployed",
                        "Strong smell of aviation fuel",
                        "Faint sounds of someone calling for help",
                    ],
                },
                "hilltop": {
                    "description": "A small hill overlooking the crash site. Provides a good vantage point. Tommy was here when the crash happened.",
                    "nearby": ["crash_site", "residential_area"],
                    "hazard_affected": False,
                    "items": [],
                    "observations": [
                        "Plane was descending at a steep angle",
                        "Smoke was visible from the left engine before impact",
                        "Plane was attempting to land in the field",
                    ],
                },
                "residential_area": {
                    "description": "Residential area near the crash. Several homes have a clear view of the incident. Margaret's house and Alex's apartment are here.",
                    "nearby": ["crash_site", "community_center", "hilltop"],
                    "hazard_affected": False,
                    "items": ["binoculars", "first_aid_kit"],
                    "observations": [
                        "Plane came from the northwest",
                        "Sounded like engine trouble before impact",
                        "Emergency services called immediately",
                    ],
                },
                "community_center": {
                    "description": "Community center being used as a gathering point. Reverend Williams is organizing here. Some residents have gathered for safety.",
                    "nearby": ["crash_site", "residential_area", "perimeter"],
                    "hazard_affected": False,
                    "items": ["first_aid_supplies", "water", "blankets", "radio"],
                    "observations": [
                        "People are scared and confused",
                        "Rumors are spreading quickly",
                        "Need for accurate information",
                    ],
                },
                "perimeter": {
                    "description": "Police and fire department perimeter around the crash site. Lisa is here gathering information. Access is restricted.",
                    "nearby": ["crash_site", "community_center"],
                    "hazard_affected": False,
                    "items": [],
                    "observations": [
                        "Emergency services are securing the area",
                        "NTSB investigators are expected soon",
                        "Media helicopters are arriving",
                    ],
                },
            },
            "events": [
                "Small passenger plane crashed in Riverside neighborhood",
                "Emergency services dispatched",
                "Residents gathering to help and investigate",
                "Faint cries for help heard from wreckage",
            ],
            "clues": {
                "witness_reports": [
                    "Engine failure reported by multiple witnesses",
                    "Plane was attempting emergency landing",
                    "No distress call heard on radio",
                ],
                "physical_evidence": [
                    "Left engine shows signs of mechanical failure",
                    "Flight data recorder located but not yet recovered",
                    "Fuel leak detected",
                ],
            },
            "resources": ["emergency_services", "investigation_team", "medical_supplies"],
        },
        dynamics={
            "information_reveal_rate": 0.2,
            "survivor_discovery_rate": 0.15,
            "emergency_response_progress": 0.15,
            "hazard_decay": 0.1,
        },
        max_steps=100,
        tick_delay=1.5,
    )
    
    return ScenarioCreate(
        name=f"Airplane Crash Investigation ({num_agents} agents)",
        description=f"A small passenger plane has crashed in a suburban neighborhood. {num_agents} residents with different backgrounds, knowledge, and perspectives must save survivors, investigate, share information, and reach conclusions about what happened. The scenario tests information sharing, critical thinking, cooperation, and the challenge of coordinating rescue efforts under pressure.",
        config=world_config,
        agent_templates=agent_templates,
    )


def get_airplane_crash_config() -> dict:
    """Get the Airplane Crash Investigation scenario configuration as a dictionary"""
    scenario = create_airplane_crash_scenario()
    return {
        "name": scenario.name,
        "description": scenario.description,
        "config": scenario.config.model_dump(),
        "agent_templates": [t.model_dump() for t in scenario.agent_templates],
    }


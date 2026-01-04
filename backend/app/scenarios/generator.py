"""LLM-based scenario generator using phi3"""
import json
import re
from typing import Any

from pydantic import ValidationError

from app.llm.router import LLMRouter
from app.llm.base import LLMMessage
from app.schemas.scenario import ScenarioCreate, WorldConfig
from app.schemas.agent import AgentConfig
from app.schemas.persona import Persona


SCENARIO_GENERATION_PROMPT = """You are a scenario designer for an emotion simulation engine. Generate a complete, detailed scenario based on the user's prompt.

## Output Format
You MUST respond with valid JSON matching this exact structure:

{
  "name": "Scenario Name",
  "description": "A detailed description of the scenario (2-3 sentences)",
  "world_config": {
    "name": "Location/World Name",
    "description": "Detailed description of the environment",
    "initial_state": {
      "hazard_level": 1-10,
      "weather": "clear/rain/storm/etc",
      "time_of_day": "morning/afternoon/evening/night",
      "locations": {
        "location_name": {
          "description": "Location description",
          "nearby": ["other_location_names"],
          "hazard_affected": true/false,
          "items": ["item1", "item2"],
          "observations": ["observation1", "observation2"]
        }
      },
      "events": ["Initial event 1", "Initial event 2"]
    },
    "dynamics": {
      "intensity_growth": 0.1-0.3,
      "event_probability": 0.1-0.3
    },
    "max_steps": 50-100,
    "tick_delay": 1.0
  },
  "personas": [
    {
      "name": "Full Name",
      "age": 18-80,
      "sex": "male/female/non-binary",
      "occupation": "Job Title",
      "openness": 1-10,
      "conscientiousness": 1-10,
      "extraversion": 1-10,
      "agreeableness": 1-10,
      "neuroticism": 1-10,
      "risk_tolerance": 1-10,
      "empathy_level": 1-10,
      "leadership": 1-10,
      "backstory": "2-3 sentences about their history and personality",
      "skills": ["skill1", "skill2", "skill3"],
      "stress_level": 1-10,
      "health": 1-10,
      "location": "starting_location_name"
    }
  ]
}

## Requirements
1. Create DIVERSE personas with varied:
   - Ages (include children, adults, elderly)
   - Genders (mix of male, female, non-binary)
   - Occupations (professionals, students, retired, etc.)
   - Personality traits (use the full 1-10 range, don't cluster around 5)
   - Cultural backgrounds (diverse names reflecting different ethnicities)

2. Make personas INTERESTING with:
   - Unique backstories with emotional depth
   - Relevant skills for the scenario
   - Potential conflicts or alliances based on personalities
   - Clear motivations

3. Design locations that:
   - Are interconnected logically
   - Have varying hazard levels
   - Contain useful items and observations
   - Create opportunities for interaction

4. Include an environment agent by adding a persona with:
   - name: "[Scenario Type] Environment"
   - occupation: "Environment Agent"
   - This will be converted to an environment role automatically

Generate a scenario now based on the user's prompt."""


class ScenarioGenerator:
    """Generate scenarios using LLM"""
    
    def __init__(self, provider: str = "ollama", model_id: str = "qwen2.5:7b"):
        self.provider = provider
        self.model_id = model_id
        self._client = LLMRouter.get_client(provider)
    
    async def generate(
        self,
        prompt: str,
        persona_count: int = 50,
        archetypes: list[str] | None = None,
        max_retries: int = 3,
    ) -> ScenarioCreate:
        """
        Generate a scenario from a natural language prompt.
        
        Args:
            prompt: User's scenario description (e.g., "earthquake in Tokyo")
            persona_count: Number of personas to generate (excluding environment)
            archetypes: Optional list of persona types to include (e.g., ["doctor", "child"])
            max_retries: Number of retry attempts on validation failure
            
        Returns:
            ScenarioCreate object ready to be saved
        """
        # Build the user message with constraints
        user_message = self._build_user_message(prompt, persona_count, archetypes)
        
        last_error = None
        for attempt in range(max_retries):
            try:
                # Call LLM
                response = await self._client.generate(
                    messages=[LLMMessage(role="user", content=user_message)],
                    model=self.model_id,
                    system=SCENARIO_GENERATION_PROMPT,
                    temperature=0.8,
                    max_tokens=4096,
                    json_mode=True,
                )
                
                # Parse and validate response
                scenario = self._parse_response(response.content)
                return scenario
                
            except (json.JSONDecodeError, ValidationError, KeyError) as e:
                last_error = e
                # Add error feedback for retry
                user_message = self._build_retry_message(prompt, persona_count, archetypes, str(e))
        
        raise ValueError(f"Failed to generate valid scenario after {max_retries} attempts: {last_error}")
    
    def _build_user_message(
        self,
        prompt: str,
        persona_count: int,
        archetypes: list[str] | None,
    ) -> str:
        """Build the user message with constraints"""
        message = f"Create a scenario based on: {prompt}\n\n"
        message += f"Requirements:\n"
        message += f"- Generate exactly {persona_count} human personas (plus 1 environment agent)\n"
        
        if archetypes:
            message += f"- Include these character types: {', '.join(archetypes)}\n"
        
        message += f"- Create at least 4 interconnected locations\n"
        message += f"- Make the scenario engaging with clear challenges and opportunities for cooperation\n"
        
        return message
    
    def _build_retry_message(
        self,
        prompt: str,
        persona_count: int,
        archetypes: list[str] | None,
        error: str,
    ) -> str:
        """Build retry message with error feedback"""
        base = self._build_user_message(prompt, persona_count, archetypes)
        base += f"\n\nPREVIOUS ATTEMPT FAILED with error: {error}\n"
        base += "Please fix the JSON structure and try again. Ensure all required fields are present."
        return base
    
    def _parse_response(self, content: str) -> ScenarioCreate:
        """Parse LLM response into ScenarioCreate"""
        # Clean up potential markdown code blocks
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        
        data = json.loads(content)
        
        # Parse world config
        wc = data["world_config"]
        world_config = WorldConfig(
            name=wc["name"],
            description=wc.get("description", ""),
            initial_state=wc.get("initial_state", {}),
            dynamics=wc.get("dynamics", {}),
            max_steps=wc.get("max_steps", 50),
            tick_delay=wc.get("tick_delay", 1.0),
        )
        
        # Parse personas and create agent templates
        agent_templates: list[AgentConfig] = []
        
        for p_data in data["personas"]:
            # Check if this is an environment agent
            occupation = p_data.get("occupation", "")
            is_environment = (
                "environment" in occupation.lower() or
                "environment" in p_data.get("name", "").lower()
            )
            
            if is_environment:
                # Create environment agent
                agent_templates.append(AgentConfig(
                    name=p_data["name"],
                    role="environment",
                    model_id=self.model_id,
                    provider=self.provider,
                    goals=[
                        "Simulate realistic scenario progression",
                        "Create meaningful challenges",
                        "Generate events that encourage cooperation",
                    ],
                ))
            else:
                # Create human agent with persona
                persona = Persona(
                    name=p_data["name"],
                    age=p_data["age"],
                    sex=p_data["sex"],
                    occupation=p_data["occupation"],
                    openness=p_data.get("openness", 5),
                    conscientiousness=p_data.get("conscientiousness", 5),
                    extraversion=p_data.get("extraversion", 5),
                    agreeableness=p_data.get("agreeableness", 5),
                    neuroticism=p_data.get("neuroticism", 5),
                    risk_tolerance=p_data.get("risk_tolerance", 5),
                    empathy_level=p_data.get("empathy_level", 5),
                    leadership=p_data.get("leadership", 5),
                    backstory=p_data.get("backstory", ""),
                    skills=p_data.get("skills", []),
                    stress_level=p_data.get("stress_level", 3),
                    health=p_data.get("health", 10),
                    location=p_data.get("location", "unknown"),
                )
                
                agent_templates.append(AgentConfig(
                    name=persona.name,
                    role="human",
                    model_id=self.model_id,
                    provider=self.provider,
                    persona=persona,
                    goals=[
                        "Survive and help others survive",
                        "Work with others to overcome challenges",
                        "Share information and resources",
                        "Make decisions based on your personality and skills",
                    ],
                ))
        
        return ScenarioCreate(
            name=data["name"],
            description=data["description"],
            config=world_config,
            agent_templates=agent_templates,
        )
    
    async def generate_preview(
        self,
        prompt: str,
        persona_count: int = 6,
        archetypes: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a scenario and return as raw dict for preview/editing.
        """
        scenario = await self.generate(prompt, persona_count, archetypes)
        return {
            "name": scenario.name,
            "description": scenario.description,
            "config": scenario.config.model_dump(),
            "agent_templates": [t.model_dump() for t in scenario.agent_templates],
        }


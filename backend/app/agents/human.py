"""Human Agent - roleplays as a person with personality"""
from typing import Any

from app.agents.base import Agent
from app.schemas.persona import Persona


class HumanAgent(Agent):
    """
    Agent that roleplays as a human with rich personality traits.
    Makes decisions based on persona characteristics and emotional state.
    """
    
    def __init__(
        self,
        agent_id: str | None = None,
        name: str = "Human",
        model_id: str = "llama3.2",
        provider: str = "ollama",
        persona: Persona | None = None,
        goals: list[str] | None = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name=name,
            role="human",
            model_id=model_id,
            provider=provider,
            goals=goals or ["Survive", "Help others if possible"],
        )
        
        # Use provided persona or create a default one
        self.persona = persona or Persona(
            name=name,
            age=30,
            sex="non-binary",
            occupation="Civilian",
        )
        
        # Sync name with persona
        self.name = self.persona.name
        
        # Initialize dynamic state from persona
        self.dynamic_state = {
            "stress_level": self.persona.stress_level,
            "health": self.persona.health,
            "inventory": self.persona.inventory.copy(),
            "location": self.persona.location,
        }
    
    def get_system_prompt(self) -> str:
        """Generate system prompt based on persona"""
        persona_description = self.persona.to_prompt_description()
        
        goals_str = "\n".join(f"- {goal}" for goal in self.goals)
        
        return f"""{persona_description}

Your Goals:
{goals_str}

Available Actions:
- move: Move to a different location
- speak: Say something to others
- help: Help another person
- take: Pick up an item
- use: Use an item from inventory
- wait: Do nothing this turn

Output your response as JSON:
{{
    "actions": [
        {{
            "action_type": "move|speak|help|take|use|wait",
            "target": "<target location/person/item>",
            "parameters": {{}}
        }}
    ],
    "message": {{
        "content": "<what you say (in character)>",
        "to_target": "<agent name or 'broadcast'>",
        "message_type": "direct|broadcast"
    }},
    "state_changes": {{
        "stress_level": <new stress 1-10 if changed>,
        "health": <new health if changed>
    }},
    "reasoning": "<brief internal thought process>"
}}

Stay in character. Your personality should influence your decisions."""
    
    def build_context(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> str:
        """Build context for human agent decisions"""
        # World state summary
        hazard_level = world_state.get("hazard_level", 0)
        current_step = world_state.get("current_step", 0)
        locations = world_state.get("locations", {})
        
        # Get location info
        current_loc = self.dynamic_state.get("location", "unknown")
        loc_info = locations.get(current_loc, {})
        
        context = f"""Current Situation (Step {current_step}):

Environment:
- Hazard Level: {hazard_level}/10 {'⚠️ DANGER!' if hazard_level >= 7 else '⚡ Concerning' if hazard_level >= 4 else '✓ Manageable'}
- Your Location: {current_loc}
- Location Status: {loc_info.get('description', 'Unknown area')}
- Nearby: {loc_info.get('nearby', [])}
- Available Items: {loc_info.get('items', [])}

Your Current State:
- Stress: {self.dynamic_state.get('stress_level', 5)}/10
- Health: {self.dynamic_state.get('health', 10)}/10
- Inventory: {self.dynamic_state.get('inventory', [])}

"""
        
        # Add messages from others
        if messages:
            context += "Recent Communications:\n"
            for msg in messages[-10:]:
                sender = msg.get("from_agent", "Unknown")
                content = msg.get("content", "")
                msg_type = msg.get("message_type", "direct")
                context += f"- [{msg_type.upper()}] {sender}: \"{content}\"\n"
        else:
            context += "No recent communications.\n"
        
        # Environmental events
        events = world_state.get("events", [])
        if events:
            context += "\nRecent Events:\n"
            for event in events[-3:]:
                context += f"- {event}\n"
        
        context += """
What do you do? Consider your personality, stress level, and the situation.
Respond in character with your action and any message you want to send."""
        
        return context
    
    def update_stress(self, delta: int) -> None:
        """Update stress level with bounds checking"""
        current = self.dynamic_state.get("stress_level", 5)
        new_level = max(1, min(10, current + delta))
        self.dynamic_state["stress_level"] = new_level
        self.persona.stress_level = new_level
    
    def update_health(self, delta: int) -> None:
        """Update health with bounds checking"""
        current = self.dynamic_state.get("health", 10)
        new_health = max(0, min(10, current + delta))
        self.dynamic_state["health"] = new_health
        self.persona.health = new_health
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize agent with persona data"""
        base = super().to_dict()
        base["persona"] = self.persona.model_dump()
        return base


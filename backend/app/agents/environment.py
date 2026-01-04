"""Environment Agent - controls world state and hazards"""
from typing import Any

from app.agents.base import Agent


class EnvironmentAgent(Agent):
    """
    Agent that controls the environment/world state.
    Manages hazards, resource spawns, and environmental dynamics.
    """
    
    def __init__(
        self,
        agent_id: str | None = None,
        name: str = "Environment",
        model_id: str = "llama3.2",
        provider: str = "ollama",
        environment_type: str = "flood",
        dynamics_config: dict[str, Any] | None = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name=name,
            role="environment",
            model_id=model_id,
            provider=provider,
            goals=["Simulate realistic environmental conditions", "Create meaningful challenges"],
        )
        
        self.environment_type = environment_type
        self.dynamics_config = dynamics_config or {
            "intensity_growth": 0.1,  # How fast hazards increase
            "resource_spawn_rate": 0.2,  # Chance of new resources
            "event_probability": 0.15,  # Chance of random events
        }
    
    def get_system_prompt(self) -> str:
        """Generate system prompt for environment agent"""
        return f"""You are the Environment Controller for a {self.environment_type} disaster simulation.

Your role is to:
1. Progress the environmental conditions realistically
2. Spawn hazards, resources, and events that create meaningful challenges
3. Respond to agent actions that affect the environment
4. Maintain dramatic tension while remaining plausible

You control:
- Hazard levels (flood water, fire spread, etc.)
- Resource availability (supplies, shelter, tools)
- Environmental events (structure collapses, rescues possible, etc.)
- Location accessibility
- Agent health and stress (through location effects and direct actions)

Output your response as JSON with this structure:
{{
    "actions": [
        {{
            "action_type": "environment_update",
            "target": "world_state",
            "parameters": {{
                "hazard_level": <number 0-10>,
                "affected_locations": ["location1", "location2"],
                "new_resources": ["resource1"],
                "events": ["event description"]
            }}
        }},
        {{
            "action_type": "affect_agent",
            "target": "<agent_id or agent_name>",
            "parameters": {{
                "health_delta": <number -10 to 10>,
                "stress_delta": <number -10 to 10>,
                "health": <number 0-10>,
                "stress_level": <number 1-10>
            }}
        }}
    ],
    "message": {{
        "content": "<narrative description of environmental changes>",
        "to_target": "broadcast",
        "message_type": "system"
    }},
    "state_changes": {{}},
    "reasoning": "<your reasoning for these changes>"
}}

Be dramatic but fair. Create challenges that test human cooperation and decision-making."""
    
    def build_context(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
        step_actions: list[dict[str, Any]] | None = None,
        step_messages: list[dict[str, Any]] | None = None,
        step_events: list[str] | None = None,
    ) -> str:
        """Build context for environment decisions"""
        # Current world state summary
        hazard_level = world_state.get("hazard_level", 0)
        current_step = world_state.get("current_step", 0)
        locations = world_state.get("locations", {})
        
        context = f"""Current Simulation State (Step {current_step}):

Environment Status:
- Hazard Level: {hazard_level}/10
- Active Locations: {list(locations.keys()) if locations else 'None defined'}

Dynamics Configuration:
- Intensity Growth Rate: {self.dynamics_config.get('intensity_growth', 0.1)}
- Resource Spawn Rate: {self.dynamics_config.get('resource_spawn_rate', 0.2)}
- Event Probability: {self.dynamics_config.get('event_probability', 0.15)}

Recent Agent Actions:
"""
        
        # Add recent relevant actions from messages
        for msg in messages[-5:]:  # Last 5 messages
            sender = msg.get("from_agent", "Unknown")
            content = msg.get("content", "")
            context += f"- {sender}: {content}\n"
        
        context += """
Based on the current state and agent actions, determine:
1. Should the hazard level increase, decrease, or stay the same?
2. Should any new resources or events be spawned?
3. Are any locations becoming inaccessible or newly accessible?

Respond with appropriate environmental updates."""
        
        return context


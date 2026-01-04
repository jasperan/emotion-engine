"""Human Agent - roleplays as a person with personality"""
import random
from typing import Any

from app.agents.base import Agent
from app.schemas.persona import Persona


class HumanAgent(Agent):
    """
    Agent that roleplays as a human with rich personality traits.
    Makes decisions based on persona characteristics and emotional state.
    Includes memory of relationships and past events.
    """
    
    def __init__(
        self,
        agent_id: str | None = None,
        name: str = "Human",
        model_id: str = "gemma3:270m",
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
        
        # Update agent memory with correct name
        self.agent_memory.agent_name = self.name
        
        # Initialize dynamic state from persona
        self.dynamic_state = {
            "stress_level": self.persona.stress_level,
            "health": self.persona.health,
            "inventory": self.persona.inventory.copy(),
            "location": self.persona.location,
        }
    
    def should_respond(
        self,
        has_events: bool,
        has_messages: bool,
        location_activity: int,
    ) -> bool:
        """Determine if agent should evaluate/respond this turn based on personality"""
        base_probability = 0.3  # Base 30% chance
        
        # Extraversion increases base probability
        extraversion_mod = (self.persona.extraversion - 5) * 0.05  # -0.2 to +0.2
        
        # Neuroticism increases reactivity to events
        neuroticism_mod = 0.0
        if has_events or has_messages:
            neuroticism_mod = (self.persona.neuroticism - 5) * 0.08  # -0.32 to +0.32
        
        # Leadership increases initiative
        leadership_mod = (self.persona.leadership - 5) * 0.03
        
        # Stress makes agents more reactive
        stress_mod = (self.persona.stress_level - 5) * 0.05
        
        # Location activity (more people = more likely to interact)
        activity_mod = min(location_activity * 0.1, 0.3)
        
        probability = base_probability + extraversion_mod + neuroticism_mod + leadership_mod + stress_mod + activity_mod
        probability = max(0.1, min(0.9, probability))  # Clamp between 10% and 90%
        
        return random.random() < probability
    
    def get_system_prompt(self) -> str:
        """Generate system prompt based on persona"""
        persona_description = self.persona.to_prompt_description()
        
        goals_str = "\n".join(f"- {goal}" for goal in self.goals)
        
        return f"""{persona_description}

Your Goals:
{goals_str}

Available Actions:
- move: Move to a different location (target = location name)
- speak: Say something to others at your location
- help: Help another person
- take: Pick up an item (target = item name)
- drop: Drop an item from inventory (target = item name)
- use: Use an item from inventory (target = item name)
- interact: Interact with an object (target = object name, parameters: {{action: "open"|"search"|etc}})
- search: Search the area for hidden items
- wait: Do nothing this turn
- join_conversation: Join a conversation with specific people
- leave_conversation: Leave the current conversation
- propose_task: Propose a task for others (parameters: description, priority, assigned_to)
- accept_task: Accept an available task (target = task_id or description)
- report_progress: Report progress on a task or goal (parameters: task_id, progress, goal, goal_progress)
- call_for_vote: Call for a vote on ending/continuing (parameters: topic, vote: "continue"|"end")

Output your response as JSON:
{{
    "actions": [
        {{
            "action_type": "move|speak|help|take|drop|use|interact|search|wait|join_conversation|leave_conversation",
            "target": "<target location/person/item>",
            "parameters": {{}}
        }}
    ],
    "message": {{
        "content": "<what you say (in character)>",
        "to_target": "<agent name or 'broadcast'>",
        "message_type": "direct|broadcast|conversation"
    }},
    "state_changes": {{
        "stress_level": <new stress 1-10 if changed>,
        "health": <new health if changed>
    }},
    "reasoning": "<brief internal thought process>"
}}

IMPORTANT:
- Stay in character. Your personality should influence your decisions.
- Consider your relationships with others when speaking.
- If you have nothing to say, you can choose not to include a message.
- Movement takes you to a new location where you'll meet different people.
- Cooperate with others! Use propose_task and accept_task to coordinate efforts.
- BE DECISIVE. Do not waste time with idle chatter if there is a crisis.
- Make clear decisions and take action. Avoid passive language like "maybe we should" or "I wonder if".
- If you notice you're repeating the same actions, check the "suggestions" in world_state.
- Work toward shared goals. Report progress when you make headway.
- If you think the situation is resolved, you can call_for_vote to suggest ending.
- Use items if they can help you or others (e.g. medical kits for health).
- Search the room if you need resources."""
    
    def build_context(
        self,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
        step_actions: list[dict[str, Any]] | None = None,
        step_messages: list[dict[str, Any]] | None = None,
        step_events: list[str] | None = None,
    ) -> str:
        """Build context for human agent decisions"""
        # World state summary
        hazard_level = world_state.get("hazard_level", 0)
        current_step = world_state.get("current_step", 0)
        locations = world_state.get("locations", {})
        agents_state = world_state.get("agents", {})
        objects = world_state.get("objects", {}) # Get object definitions
        
        # Get location info
        current_loc = self.dynamic_state.get("location", "unknown")
        loc_info = locations.get(current_loc, {})
        
        # Get agents at this location
        agents_here = []
        for agent_id, agent_info in agents_state.items():
            if agent_info.get("location") == current_loc and agent_id != self.id:
                agents_here.append(agent_info.get("name", agent_id))
        
        # Process items and interactables
        visible_items = []
        loc_items = loc_info.get("items", [])
        for item_ref in loc_items:
            # item_ref can be a string ID or a dict (legacy)
            if isinstance(item_ref, str):
                item_def = objects.get(item_ref, {"name": item_ref})
                if isinstance(item_def, dict):
                    name = item_def.get("name", item_ref)
                    if item_def.get("is_visible", True):
                        visible_items.append(name)
            elif isinstance(item_ref, dict):
                 if item_ref.get("is_visible", True):
                    visible_items.append(item_ref.get("name", "Unknown Item"))
        
        # Process inventory
        inventory_list = []
        for item in self.inventory:
            # Item object or dict
            if hasattr(item, "name"):
                inventory_list.append(item.name)
            elif isinstance(item, dict):
                inventory_list.append(item.get("name", "Unknown Item"))

        # Build context string
        context = f"""Current Situation (Step {current_step}):

Environment:
- Hazard Level: {hazard_level}/10 {'⚠️ DANGER!' if hazard_level >= 7 else '⚡ Concerning' if hazard_level >= 4 else '✓ Manageable'}
- Your Location: {current_loc}
- Location Status: {loc_info.get('description', 'Unknown area')}
- People Here: {', '.join(agents_here) if agents_here else 'No one else'}
- Nearby Locations: {loc_info.get('nearby', [])}
- Visible Items/Objects: {', '.join(visible_items) if visible_items else 'None visible'}

Your Current State:
- Stress: {self.dynamic_state.get('stress_level', 5)}/10
- Health: {self.dynamic_state.get('health', 10)}/10
- Inventory: {', '.join(inventory_list) if inventory_list else 'Empty'}

"""
        
        # Add conversation context if in an active conversation
        active_conversation = world_state.get("active_conversation")
        if active_conversation:
            context += f"""Active Conversation:
- Location: {active_conversation.get('location', 'here')}
- Participants: {', '.join(active_conversation.get('participants', []))}
- It is your turn to speak (or you can stay silent).

"""
        
        # Add memory context (relationships and past events)
        memory_context = self.get_conversation_context()
        if memory_context:
            context += f"Your Memory:\n{memory_context}\n\n"
        
        # Add relationship context for people here
        if agents_here:
            # Get agent IDs for people here
            agent_ids_here = [
                aid for aid, info in agents_state.items()
                if info.get("name") in agents_here
            ]
            relationship_context = self.get_relationship_context(agent_ids_here)
            if relationship_context:
                context += f"Your Relationships with People Here:\n{relationship_context}\n\n"
        
        # Add messages from others
        if messages:
            context += "Recent Communications:\n"
            for msg in messages[-15:]:
                sender = msg.get("from_agent_name", msg.get("from_agent", "Unknown"))
                content = msg.get("content", "")
                msg_type = msg.get("message_type", "direct")
                context += f"- [{msg_type.upper()}] {sender}: \"{content}\"\n"
            context += "\n"
        else:
            context += "No recent communications.\n\n"
        
        # Step-specific events (events that happened in this step)
        if step_events:
            context += "Events This Step:\n"
            for event in step_events:
                context += f"- {event}\n"
            context += "\n"
        
        # Recent actions from this step (what other agents have done)
        if step_actions:
            context += "Recent Actions This Step:\n"
            for action in step_actions[-10:]:  # Show last 10 actions
                agent_name = action.get("agent_name", action.get("agent_id", "Unknown"))
                action_type = action.get("action_type", "unknown")
                target = action.get("target", "")
                if target:
                    context += f"- {agent_name} {action_type} to {target}\n"
                else:
                    context += f"- {agent_name} {action_type}\n"
            context += "\n"
        
        # Recent messages from this step (what other agents have said)
        if step_messages:
            context += "Recent Messages This Step:\n"
            for msg in step_messages[-10:]:  # Show last 10 messages
                sender = msg.get("from_agent_name", msg.get("from_agent", "Unknown"))
                content = msg.get("content", "")
                msg_type = msg.get("message_type", "direct")
                context += f"- [{msg_type.upper()}] {sender}: \"{content}\"\n"
            context += "\n"
        
        # Environmental events (historical)
        events = world_state.get("events", [])
        if events and not step_events:  # Only show if no step-specific events
            context += "Recent Events:\n"
            for event in events[-3:]:
                context += f"- {event}\n"
            context += "\n"
        
        # Action prompt
        if active_conversation and active_conversation.get("is_my_turn"):
            context += """It's your turn in the conversation. What do you say?
Consider what others have said and respond naturally. 
You can also choose to stay silent by not including a message.
Think about your relationships and personality when responding."""
        else:
            context += """What do you do? Consider your personality, stress level, and the situation.
Respond in character with your action and any message you want to send.
You can move to a nearby location if you want to leave."""
        
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
    
    def update_relationship(
        self,
        agent_id: str,
        trust_delta: int = 0,
        sentiment: str | None = None,
        note: str | None = None,
    ) -> None:
        """Update relationship with another agent"""
        self.agent_memory.update_relationship(
            agent_id=agent_id,
            trust_delta=trust_delta,
            sentiment=sentiment,
            note=note,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize agent with persona data"""
        base = super().to_dict()
        base["persona"] = self.persona.model_dump()
        return base

"""Simulation Engine - main orchestrator for runs"""
import asyncio
import random
from datetime import datetime
from typing import Any, Callable
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import Agent, EnvironmentAgent, HumanAgent, DesignerAgent, EvaluationAgent
from app.simulation.message_bus import MessageBus
from app.simulation.conversation import ConversationManager, Conversation, ConversationState
from app.models.run import Run, RunStatus
from app.models.agent import AgentModel
from app.models.step import Step
from app.models.message import Message, MessageType
from app.schemas.persona import Persona


class SimulationState(str, Enum):
    """Current state of the simulation engine"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETING = "completing"
    ERROR = "error"


class SimulationEngine:
    """
    Main simulation engine that orchestrates runs.
    Manages agent lifecycle, tick loop, conversations, and state persistence.
    """
    
    def __init__(
        self,
        run_id: str,
        db_session: AsyncSession,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        self.run_id = run_id
        self.db = db_session
        self.on_event = on_event or (lambda t, d: None)
        
        self.state = SimulationState.IDLE
        self.current_step = 0
        self.max_steps = 100
        self.tick_delay = 0.5
        
        # World state
        self.world_state: dict[str, Any] = {
            "hazard_level": 0,
            "locations": {},
            "resources": [],
            "events": [],
        }
        
        # Agents
        self.agents: dict[str, Agent] = {}
        self.message_bus = MessageBus()
        
        # Conversation management
        self.conversation_manager = ConversationManager()
        
        # Cooperation coordinator
        from app.agents.coordinator import CooperationCoordinator
        self.coordinator = CooperationCoordinator()
        
        # Real-time agent locations (updated during steps)
        self._agent_locations: dict[str, str] = {}
        
        # Control
        self._stop_requested = False
        self._pause_requested = False
        self._step_event = asyncio.Event()
    
    async def initialize(self, scenario_config: dict[str, Any]) -> None:
        """Initialize the simulation from scenario config"""
        self.state = SimulationState.INITIALIZING
        
        # Set world parameters
        world_config = scenario_config.get("config", {})
        # Default to None (infinite) unless explicitly set
        self.max_steps = world_config.get("max_steps", None)
        self.tick_delay = world_config.get("tick_delay", 0.5)
        
        self.world_state.update(world_config.get("initial_state", {}))
        
        # Initialize seed if provided
        seed = scenario_config.get("seed")
        if seed is not None:
            random.seed(seed)
        
        # Create agents from templates
        agent_templates = scenario_config.get("agent_templates", [])
        for template in agent_templates:
            agent = self._create_agent(template)
            self.agents[agent.id] = agent
            self.message_bus.register_agent(agent.id, agent.name)
            
            # Initialize agent location in conversation manager
            agent_location = agent.dynamic_state.get("location", "unknown")
            self._agent_locations[agent.id] = agent_location
            self.conversation_manager.update_agent_location(agent.id, agent_location)
            # Subscribe agent to location room for room messages
            self.message_bus.join_room(agent.id, agent_location)
            
            # Persist agent to database
            agent_model = AgentModel(
                id=agent.id,
                run_id=self.run_id,
                role=agent.role,
                name=agent.name,
                model_id=agent.model_id,
                provider=agent.provider,
                persona=agent.to_dict().get("persona", {}),
                dynamic_state=agent.dynamic_state,
            )
            self.db.add(agent_model)
        
        await self.db.commit()
        
        # Initialize shared goals from agent goals
        all_goals = set()
        for agent in self.agents.values():
            if agent.role == "human" and hasattr(agent, 'goals'):
                all_goals.update(agent.goals)
        
        for goal in all_goals:
            self.coordinator.add_shared_goal(goal)
        
        # Add cooperation context to world state
        self.world_state["shared_goals"] = self.coordinator.shared_goals
        self.world_state["cooperation"] = self.coordinator.get_cooperation_context()
        
        self.state = SimulationState.IDLE
        self.on_event("initialized", {"agent_count": len(self.agents)})
    
    def _create_agent(self, config: dict[str, Any]) -> Agent:
        """Create an agent from configuration"""
        role = config.get("role", "human")
        
        if role == "environment":
            return EnvironmentAgent(
                name=config.get("name", "Environment"),
                model_id=config.get("model_id", "llama3.2"),
                provider=config.get("provider", "ollama"),
                environment_type=config.get("environment_type", "flood"),
                dynamics_config=config.get("dynamics_config"),
            )
        elif role == "designer":
            return DesignerAgent(
                name=config.get("name", "Director"),
                model_id=config.get("model_id", "llama3.2"),
                provider=config.get("provider", "ollama"),
                scenario_goals=config.get("goals"),
            )
        elif role == "evaluator":
            return EvaluationAgent(
                name=config.get("name", "Evaluator"),
                model_id=config.get("model_id", "llama3.2"),
                provider=config.get("provider", "ollama"),
            )
        else:  # human
            persona_data = config.get("persona", {})
            persona = Persona(**persona_data) if persona_data else None
            
            return HumanAgent(
                name=config.get("name", "Human"),
                model_id=config.get("model_id", "llama3.2"),
                provider=config.get("provider", "ollama"),
                persona=persona,
                goals=config.get("goals"),
            )
    
    async def start(self) -> None:
        """Start the simulation run"""
        if self.state not in (SimulationState.IDLE, SimulationState.PAUSED):
            return
        
        self.state = SimulationState.RUNNING
        self._stop_requested = False
        self._pause_requested = False
        
        # Update run status in DB
        run = await self.db.get(Run, self.run_id)
        if run:
            run.status = RunStatus.RUNNING
            run.started_at = run.started_at or datetime.utcnow()
            await self.db.commit()
        
        self.on_event("run_started", {"step": self.current_step})
        
        # Main simulation loop
        await self._run_loop()
    
    async def _run_loop(self) -> None:
        """Main simulation loop"""
        # Safety limit to prevent infinite runs
        MAX_SAFETY_STEPS = 1000
        
        while (
            (self.max_steps is None or self.current_step < self.max_steps)
            and self.current_step < MAX_SAFETY_STEPS
            and not self._stop_requested
            and self.state == SimulationState.RUNNING
            and not self._check_consensus()
        ):
            if self._pause_requested:
                self.state = SimulationState.PAUSED
                self._pause_requested = False
                self.on_event("run_paused", {"step": self.current_step})
                return
            
            await self._execute_step()
            
            # Wait between ticks
            await asyncio.sleep(self.tick_delay)
        
        # Run completed
        if not self._stop_requested:
            await self._complete_run()
    
    async def _execute_step(self) -> None:
        """Execute a single simulation step with sequential agent processing"""
        self.current_step += 1
        self.world_state["current_step"] = self.current_step
        
        step_actions = []
        step_messages = []
        step_events = []
        
        # Reset conversation counters for this step
        self.conversation_manager.reset_step_counters()
        
        # Build current agent states for world state
        self._update_agents_in_world_state()
        
        # Process all agents sequentially
        await self._process_agents_sequentially(step_actions, step_messages, step_events)
        
        # Cleanup ended conversations
        self.conversation_manager.cleanup_ended_conversations()
        
        # Persist step
        step = Step(
            run_id=self.run_id,
            step_index=self.current_step,
            state_snapshot=self.world_state.copy(),
            actions=step_actions,
            step_metrics=self._compute_step_metrics(),
        )
        self.db.add(step)
        
        # Update run
        run = await self.db.get(Run, self.run_id)
        if run:
            run.current_step = self.current_step
            run.world_state = self.world_state.copy()
        
        await self.db.commit()
        
        # Emit step event
        self.on_event("step_completed", {
            "step": self.current_step,
            "actions": step_actions,
            "messages": step_messages,
            "world_state": self.world_state,
            "conversations": [c.to_dict() for c in self.conversation_manager.get_all_active_conversations()],
        })
    
    def _update_agents_in_world_state(self) -> None:
        """Update world state with current agent information"""
        agents_state = {}
        for agent_id, agent in self.agents.items():
            location = self._agent_locations.get(agent_id, agent.dynamic_state.get("location", "unknown"))
            agents_state[agent_id] = {
                "name": agent.name,
                "role": agent.role,
                "location": location,
                **agent.dynamic_state,
            }
        self.world_state["agents"] = agents_state
    
    async def _process_agents_sequentially(
        self,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
        step_events: list[str],
    ) -> None:
        """Process all agents sequentially so they can see each other's actions"""
        # Phase 1: Process environment agents first (they create events)
        for agent_id, agent in self.agents.items():
            if agent.role != "environment":
                continue
            
            messages = self.message_bus.get_messages(agent_id)
            
            try:
                response = await agent.tick(
                    self.world_state.copy(),
                    messages,
                    step_actions,
                    step_messages,
                    step_events,
                )
                
                for action in response.actions:
                    action_dict = {
                        "agent_id": agent_id,
                        "agent_name": agent.name,
                        **action.model_dump(),
                    }
                    step_actions.append(action_dict)
                    
                    if action.action_type == "environment_update":
                        self._apply_environment_update(action.parameters)
                        # Extract events if any
                        if "events" in action.parameters:
                            step_events.extend(action.parameters["events"])
                
                if response.message:
                    msg = response.message
                    stored_msg = self.message_bus.broadcast(
                        agent_id, msg.content, self.current_step
                    )
                    step_messages.append(stored_msg)
                    await self._persist_message(agent_id, msg)
                
                # Update world state after environment agent
                self._update_agents_in_world_state()
                    
            except Exception as e:
                agent = self.agents.get(agent_id)
                agent_name = agent.name if agent else agent_id
                self.on_event("agent_error", {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "error": str(e),
                    "step": self.current_step,
                    "context": "environment_agent_tick",
                })
        
        # Phase 2: Process human agents sequentially
        # Get all human agents, shuffled for variety
        human_agents = [
            (agent_id, agent)
            for agent_id, agent in self.agents.items()
            if agent.role == "human"
        ]
        random.shuffle(human_agents)
        
        for agent_id, agent in human_agents:
            # Check if agent is in a conversation and it's their turn
            in_conversation = False
            conversation = None
            
            agent_conversations = self.conversation_manager.get_agent_conversations(agent_id)
            for conv in agent_conversations:
                if conv.should_continue() and conv.get_next_speaker() == agent_id:
                    in_conversation = True
                    conversation = conv
                    break
            
            # For human agents not in conversations, check if they should respond (personality-based probability)
            if isinstance(agent, HumanAgent) and not in_conversation:
                # Count location activity
                agent_location = self._agent_locations.get(agent_id, agent.dynamic_state.get("location", "unknown"))
                location_activity = len([
                    aid for aid, loc in self._agent_locations.items()
                    if loc == agent_location and aid != agent_id
                ])
                
                # Check for events and messages
                has_events = len(step_events) > 0
                has_messages = len(step_messages) > 0
                
                # Check if agent should respond
                if not agent.should_respond(has_events, has_messages, location_activity):
                    continue  # Skip this agent this turn
            
            # Get messages for this agent
            messages = self.message_bus.get_messages(agent_id)
            
            # Build world state with conversation context if applicable
            agent_world_state = self.world_state.copy()
            
            # Add cooperation context
            cooperation_context = self.coordinator.get_cooperation_context()
            agent_world_state["cooperation"] = cooperation_context
            
            # Add suggestions if agent is stuck
            if self.coordinator.is_stuck_in_loop(agent_id):
                suggestions = self.coordinator.get_suggestions_for_agent(agent_id)
                agent_world_state["suggestions"] = suggestions
            
            # Add agent's assigned tasks
            agent_tasks = self.coordinator.agent_tasks.get(agent_id, [])
            agent_world_state["my_tasks"] = [
                {
                    "id": self.coordinator.tasks[tid].id,
                    "description": self.coordinator.tasks[tid].description,
                    "priority": self.coordinator.tasks[tid].priority,
                    "status": self.coordinator.tasks[tid].status,
                }
                for tid in agent_tasks
                if tid in self.coordinator.tasks
            ]
            
            if in_conversation and conversation:
                # Add conversation context
                conversation_context = conversation.get_context_for_agent(agent_id)
                messages = conversation_context + messages
                
                agent_world_state["active_conversation"] = {
                    "id": conversation.id,
                    "location": conversation.location,
                    "participants": [
                        self.agents[pid].name if pid in self.agents else pid
                        for pid in conversation.participants
                    ],
                    "is_my_turn": True,
                }
            
            try:
                response = await agent.tick(
                    agent_world_state,
                    messages,
                    step_actions,
                    step_messages,
                    step_events,
                )
                
                # Process actions
                for action in response.actions:
                    action_dict = {
                        "agent_id": agent_id,
                        "agent_name": agent.name,
                        **action.model_dump(),
                    }
                    step_actions.append(action_dict)
                    
                    # Track action for loop detection
                    self.coordinator.track_action(agent_id, action.action_type, action.target)
                    
                    # Handle movement
                    if action.action_type == "move":
                        await self._handle_movement(agent_id, action.target, action.parameters)
                    elif action.action_type == "propose_task":
                        self._handle_propose_task(agent_id, action.parameters)
                    elif action.action_type == "accept_task":
                        self._handle_accept_task(agent_id, action.target, action.parameters)
                    elif action.action_type == "report_progress":
                        self._handle_report_progress(agent_id, action.parameters)
                    elif action.action_type == "call_for_vote":
                        self._handle_call_for_vote(agent_id, action.parameters)
                
                # Track conversation topic for loop detection
                if response.message and response.message.content.strip():
                    topic = self._extract_topic(response.message.content)
                    self.coordinator.track_conversation(agent_id, topic)
                
                # Process message
                if response.message and response.message.content.strip():
                    msg = response.message
                    
                    if in_conversation and conversation:
                        # Send to conversation participants
                        stored_msg = self.message_bus.send_to_conversation(
                            from_agent_id=agent_id,
                            conversation_id=conversation.id,
                            participant_ids=conversation.participants,
                            content=msg.content,
                            step_index=self.current_step,
                            location=conversation.location,
                        )
                        conversation.add_message(stored_msg)
                        conversation.advance_turn(spoke=True)
                    else:
                        # Send as regular message (direct, room, or broadcast)
                        if msg.message_type == "broadcast":
                            stored_msg = self.message_bus.broadcast(
                                agent_id, msg.content, self.current_step
                            )
                        elif msg.message_type == "room":
                            # Send to all agents at location using room mechanism
                            agent_location = self._agent_locations.get(agent_id, agent.dynamic_state.get("location", "unknown"))
                            # Ensure all agents at location are subscribed to the room
                            agents_at_location = [
                                aid for aid, loc in self._agent_locations.items()
                                if loc == agent_location
                            ]
                            for aid in agents_at_location:
                                self.message_bus.join_room(aid, agent_location)
                            
                            stored_msg = self.message_bus.send_to_room(
                                from_agent_id=agent_id,
                                room_name=agent_location,
                                content=msg.content,
                                step_index=self.current_step,
                            )
                        else:  # direct
                            # Resolve agent name to ID if needed
                            to_agent_id = msg.to_target
                            if to_agent_id != "broadcast":
                                # Try to find agent by name
                                for aid, a in self.agents.items():
                                    if a.name == to_agent_id:
                                        to_agent_id = aid
                                        break
                            
                            stored_msg = self.message_bus.send_direct(
                                from_agent_id=agent_id,
                                to_agent_id=to_agent_id,
                                content=msg.content,
                                step_index=self.current_step,
                            )
                    
                    step_messages.append(stored_msg)
                    await self._persist_message(agent_id, msg, conversation.id if in_conversation else None)
                elif in_conversation and conversation:
                    # Agent chose not to speak in conversation
                    conversation.advance_turn(spoke=False)
                
                # Update world state after each agent
                self._update_agents_in_world_state()
                    
            except Exception as e:
                agent = self.agents.get(agent_id)
                agent_name = agent.name if agent else agent_id
                self.on_event("agent_error", {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "error": str(e),
                    "step": self.current_step,
                    "context": "environment_agent_tick",
                })
                if in_conversation and conversation:
                    conversation.advance_turn(spoke=False)
    
    async def _process_environment_agents(
        self,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
    ) -> None:
        """Process environment agent updates"""
        for agent_id, agent in self.agents.items():
            if agent.role != "environment":
                continue
            
            messages = self.message_bus.get_messages(agent_id)
            
            try:
                response = await agent.tick(self.world_state.copy(), messages)
                
                for action in response.actions:
                    step_actions.append({
                        "agent_id": agent_id,
                        "agent_name": agent.name,
                        **action.model_dump(),
                    })
                    
                    if action.action_type == "environment_update":
                        self._apply_environment_update(action.parameters)
                    elif action.action_type == "affect_agent":
                        self._apply_agent_effect(action.target, action.parameters)
                
                if response.message:
                    msg = response.message
                    stored_msg = self.message_bus.broadcast(
                        agent_id, msg.content, self.current_step
                    )
                    step_messages.append(stored_msg)
                    await self._persist_message(agent_id, msg)
                    
            except Exception as e:
                agent = self.agents.get(agent_id)
                agent_name = agent.name if agent else agent_id
                self.on_event("agent_error", {
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "error": str(e),
                    "step": self.current_step,
                    "context": "environment_agent_tick",
                })
    
    async def _process_conversations(
        self,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
    ) -> None:
        """Process multi-turn conversations until they conclude"""
        max_conversation_rounds = 10  # Safety limit
        round_count = 0
        
        while round_count < max_conversation_rounds:
            round_count += 1
            
            # Get all conversations that need processing
            active_conversations = self.conversation_manager.get_conversations_needing_turns()
            
            if not active_conversations:
                break
            
            # Process each conversation
            any_activity = False
            
            for conv in active_conversations:
                activity = await self._process_single_conversation(
                    conv, step_actions, step_messages
                )
                any_activity = any_activity or activity
            
            # If no conversation had activity, we're done
            if not any_activity:
                break
    
    async def _process_single_conversation(
        self,
        conversation: Conversation,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
    ) -> bool:
        """Process a single conversation turn. Returns True if there was activity."""
        if not conversation.should_continue():
            return False
        
        # Get the next speaker
        speaker_id = conversation.get_next_speaker()
        if not speaker_id or speaker_id not in self.agents:
            conversation.advance_turn(spoke=False)
            return False
        
        agent = self.agents[speaker_id]
        
        # Skip non-human agents in conversations (they're handled separately)
        if agent.role != "human":
            conversation.advance_turn(spoke=False)
            return False
        
        # Build context for this agent including conversation history
        conversation_context = conversation.get_context_for_agent(speaker_id)
        pending_messages = self.message_bus.get_messages(speaker_id)
        
        # Combine conversation history with any pending messages
        all_messages = conversation_context + pending_messages
        
        # Add conversation metadata to world state
        conv_world_state = self.world_state.copy()
        conv_world_state["active_conversation"] = {
            "id": conversation.id,
            "location": conversation.location,
            "participants": [
                self.agents[pid].name if pid in self.agents else pid
                for pid in conversation.participants
            ],
            "is_my_turn": True,
        }
        
        try:
            response = await agent.tick(conv_world_state, all_messages)
            
            # Process actions (including movement)
            for action in response.actions:
                step_actions.append({
                    "agent_id": speaker_id,
                    "agent_name": agent.name,
                    **action.model_dump(),
                })
                
                # Handle movement within the step
                if action.action_type == "move":
                    await self._handle_movement(speaker_id, action.target, action.parameters)
            
            # Process message
            if response.message and response.message.content.strip():
                msg = response.message
                
                # Send to conversation participants
                stored_msg = self.message_bus.send_to_conversation(
                    from_agent_id=speaker_id,
                    conversation_id=conversation.id,
                    participant_ids=conversation.participants,
                    content=msg.content,
                    step_index=self.current_step,
                    location=conversation.location,
                )
                
                # Add to conversation history
                conversation.add_message(stored_msg)
                step_messages.append(stored_msg)
                
                # Persist to database
                await self._persist_message(speaker_id, msg, conversation.id)
                
                conversation.advance_turn(spoke=True)
                return True
            else:
                # Agent chose not to speak
                conversation.advance_turn(spoke=False)
                return False
                
        except Exception as e:
            agent = self.agents.get(speaker_id)
            agent_name = agent.name if agent else speaker_id
            self.on_event("agent_error", {
                "agent_id": speaker_id,
                "agent_name": agent_name,
                "error": str(e),
                "step": self.current_step,
                "conversation_id": conversation.id,
                "context": "conversation_speak",
            })
            conversation.advance_turn(spoke=False)
            return False
    
    async def _handle_movement(
        self,
        agent_id: str,
        target_location: str | None,
        parameters: dict[str, Any],
    ) -> None:
        """Handle agent movement between locations"""
        if not target_location:
            return
        
        current_location = self._agent_locations.get(agent_id, "unknown")
        
        # Validate movement (target must be nearby)
        locations = self.world_state.get("locations", {})
        current_loc_data = locations.get(current_location, {})
        nearby = current_loc_data.get("nearby", [])
        
        # Check if target location exists - if not, dynamically register it
        if target_location not in locations:
            # Dynamically register the new location
            agent = self.agents.get(agent_id)
            agent_name = agent.name if agent else agent_id
            
            # Create new location with reasonable defaults
            locations[target_location] = {
                "description": f"A newly discovered area: {target_location}",
                "nearby": [current_location] if current_location in locations else [],
                "items": [],
                "hazard_affected": False,
            }
            
            # Make it bidirectionally connected to current location
            if current_location in locations:
                current_nearby = locations[current_location].get("nearby", [])
                if target_location not in current_nearby:
                    current_nearby.append(target_location)
                    locations[current_location]["nearby"] = current_nearby
            
            # Update world state
            self.world_state["locations"] = locations
            
            # Log the new location creation
            self.on_event("location_created", {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "location": target_location,
                "connected_to": current_location,
                "step": self.current_step,
            })
            
            # Update nearby list for validation below
            nearby = current_loc_data.get("nearby", [])
        
        if target_location not in nearby and target_location != current_location:
            # Invalid movement - location not reachable
            agent = self.agents.get(agent_id)
            agent_name = agent.name if agent else agent_id
            self.on_event("movement_failed", {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "from": current_location,
                "to": target_location,
                "reason": "Location not reachable from current location",
                "available_locations": list(locations.keys()),
                "nearby_locations": nearby,
            })
            return
        
        # Update location
        self._agent_locations[agent_id] = target_location
        
        # Update agent's dynamic state
        agent = self.agents.get(agent_id)
        if agent:
            agent.dynamic_state["location"] = target_location
        
        # Subscribe agent to location room for room messages
        self.message_bus.join_room(agent_id, target_location)
        
        # Update conversation manager (handles join/leave of location conversations)
        self.conversation_manager.update_agent_location(agent_id, target_location)
        
        # Update world state
        self._update_agents_in_world_state()
        
        agent = self.agents.get(agent_id)
        agent_name = agent.name if agent else agent_id
        self.on_event("agent_moved", {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "from": current_location,
            "to": target_location,
            "step": self.current_step,
        })
    
    async def _persist_message(
        self,
        agent_id: str,
        msg: Any,
        conversation_id: str | None = None,
    ) -> None:
        """Persist a message to the database"""
        # Determine message type
        msg_type = msg.message_type if hasattr(msg, 'message_type') else "broadcast"
        if conversation_id:
            msg_type = "conversation"
        
        # Map to MessageType enum
        try:
            db_msg_type = MessageType(msg_type)
        except ValueError:
            db_msg_type = MessageType.BROADCAST
        
        db_message = Message(
            run_id=self.run_id,
            from_agent_id=agent_id,
            to_target=conversation_id or msg.to_target,
            message_type=db_msg_type,
            content=msg.content,
            step_index=self.current_step,
            metadata={"conversation_id": conversation_id} if conversation_id else {},
        )
        self.db.add(db_message)
    
    def _apply_environment_update(self, params: dict[str, Any]) -> None:
        """Apply environment agent updates to world state"""
        if "hazard_level" in params:
            self.world_state["hazard_level"] = params["hazard_level"]
        
        if "events" in params:
            self.world_state.setdefault("events", []).extend(params["events"])
        
        if "new_resources" in params:
            self.world_state.setdefault("resources", []).extend(params["new_resources"])
        
        if "affected_locations" in params:
            for loc in params["affected_locations"]:
                self.world_state.setdefault("locations", {})[loc] = {
                    "hazard_affected": True,
                }
        
        # Apply location-based health effects
        self._apply_location_health_effects()
    
    def _apply_agent_effect(self, target_agent_id: str | None, params: dict[str, Any]) -> None:
        """Apply direct health/stress effects to a specific agent"""
        if not target_agent_id:
            return
        
        # Try to find agent by ID first, then by name
        agent = self.agents.get(target_agent_id)
        if not agent:
            # Search by name
            for agent_id, a in self.agents.items():
                if a.name == target_agent_id:
                    agent = a
                    break
        
        if not agent:
            return
        
        # Apply health changes
        if "health_delta" in params:
            current_health = agent.dynamic_state.get("health", 10)
            # Convert to float in case it's stored as string
            try:
                current_health = float(current_health)
            except (ValueError, TypeError):
                current_health = 10
            new_health = max(0, min(10, current_health + params["health_delta"]))
            agent.dynamic_state["health"] = new_health
        
        if "health" in params:
            agent.dynamic_state["health"] = max(0, min(10, params["health"]))
        
        # Apply stress changes
        if "stress_delta" in params:
            current_stress = agent.dynamic_state.get("stress_level", 1)
            # Convert to float in case it's stored as string
            try:
                current_stress = float(current_stress)
            except (ValueError, TypeError):
                current_stress = 1
            new_stress = max(1, min(10, current_stress + params["stress_delta"]))
            agent.dynamic_state["stress_level"] = new_stress
        
        if "stress_level" in params:
            agent.dynamic_state["stress_level"] = max(1, min(10, params["stress_level"]))
    
    def _apply_location_health_effects(self) -> None:
        """Apply health effects based on agent locations and location properties"""
        locations = self.world_state.get("locations", {})
        hazard_level = self.world_state.get("hazard_level", 0)
        
        for agent_id, agent in self.agents.items():
            if agent.role != "human":
                continue
            
            location = agent.dynamic_state.get("location", "unknown")
            if location not in locations:
                continue
            
            loc_data = locations[location]
            
            # Apply location effects
            location_effects = loc_data.get("location_effects", {})
            if "health_per_tick" in location_effects:
                current_health = agent.dynamic_state.get("health", 10)
                # Convert to float in case it's stored as string
                try:
                    current_health = float(current_health)
                except (ValueError, TypeError):
                    current_health = 10
                new_health = max(0, min(10, current_health + location_effects["health_per_tick"]))
                agent.dynamic_state["health"] = new_health
            
            if "stress_per_tick" in location_effects:
                current_stress = agent.dynamic_state.get("stress_level", 1)
                # Convert to float in case it's stored as string
                try:
                    current_stress = float(current_stress)
                except (ValueError, TypeError):
                    current_stress = 1
                new_stress = max(1, min(10, current_stress + location_effects["stress_per_tick"]))
                agent.dynamic_state["stress_level"] = new_stress
            
            # Apply item-based effects
            items = loc_data.get("items", [])
            for item in items:
                # First aid kits increase health
                if "first_aid" in item.lower() or "medical" in item.lower():
                    current_health = agent.dynamic_state.get("health", 10)
                    if current_health < 10:
                        agent.dynamic_state["health"] = min(10, current_health + 0.5)
                
                # Contaminated items reduce health
                if "contaminated" in item.lower() or "toxic" in item.lower():
                    current_health = agent.dynamic_state.get("health", 10)
                    agent.dynamic_state["health"] = max(0, current_health - 0.5)
            
            # Apply hazard-based effects if location is hazard-affected
            if loc_data.get("hazard_affected", False) and hazard_level > 0:
                # Higher hazard levels cause more health loss
                health_loss = (hazard_level / 10.0) * 0.3
                current_health = agent.dynamic_state.get("health", 10)
                agent.dynamic_state["health"] = max(0, current_health - health_loss)
                
                # Hazard also increases stress
                stress_gain = (hazard_level / 10.0) * 0.2
                current_stress = agent.dynamic_state.get("stress_level", 1)
                agent.dynamic_state["stress_level"] = min(10, current_stress + stress_gain)
    
    def _extract_topic(self, message: str) -> str:
        """Extract a topic/keyword from a message for loop detection"""
        # Simple keyword extraction
        keywords = [
            "rescue", "help", "move", "safety", "flood", "bridge", "shelter",
            "medical", "supplies", "coordinate", "plan", "danger", "evacuate"
        ]
        message_lower = message.lower()
        for keyword in keywords:
            if keyword in message_lower:
                return keyword
        return "general"
    
    def _handle_propose_task(self, agent_id: str, params: dict[str, Any]) -> None:
        """Handle task proposal from an agent"""
        description = params.get("description", "")
        priority = params.get("priority", 5)
        assigned_to = params.get("assigned_to")
        
        if description:
            task_id = self.coordinator.create_task(description, priority, assigned_to)
            self.on_event("task_proposed", {
                "agent_id": agent_id,
                "task_id": task_id,
                "description": description,
                "priority": priority,
            })
    
    def _handle_accept_task(self, agent_id: str, task_id: str | None, params: dict[str, Any]) -> None:
        """Handle task acceptance by an agent"""
        if not task_id:
            # Try to find task by description
            description = params.get("description", "")
            for tid, task in self.coordinator.tasks.items():
                if task.description == description and task.status == "pending":
                    task_id = tid
                    break
        
        if task_id and self.coordinator.assign_task(task_id, agent_id):
            agent = self.agents.get(agent_id)
            agent_name = agent.name if agent else agent_id
            self.on_event("task_accepted", {
                "agent_id": agent_id,
                "agent_name": agent_name,
                "task_id": task_id,
            })
    
    def _handle_report_progress(self, agent_id: str, params: dict[str, Any]) -> None:
        """Handle progress report from an agent"""
        task_id = params.get("task_id")
        progress = params.get("progress", 0.0)
        goal = params.get("goal")
        
        if task_id and task_id in self.coordinator.tasks:
            task = self.coordinator.tasks[task_id]
            task.progress = max(0.0, min(1.0, progress))
            if progress >= 1.0:
                self.coordinator.complete_task(task_id)
        
        if goal:
            goal_progress = params.get("goal_progress", 0.0)
            self.coordinator.update_goal_progress(goal, goal_progress)
    
    def _handle_call_for_vote(self, agent_id: str, params: dict[str, Any]) -> None:
        """Handle vote call from an agent (for consensus detection)"""
        topic = params.get("topic", "general")
        vote = params.get("vote", "continue")  # continue, end, pause
        
        # Store vote in world state for consensus detection
        if "votes" not in self.world_state:
            self.world_state["votes"] = {}
        
        self.world_state["votes"][agent_id] = {
            "topic": topic,
            "vote": vote,
            "step": self.current_step,
        }
        
        agent = self.agents.get(agent_id)
        agent_name = agent.name if agent else agent_id
        self.on_event("vote_cast", {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "topic": topic,
            "vote": vote,
        })
    
    def _check_consensus(self) -> bool:
        """Check if agents have reached consensus to end the simulation"""
        votes = self.world_state.get("votes", {})
        if not votes:
            return False
        
        # Get human agents
        human_agents = [aid for aid, agent in self.agents.items() if agent.role == "human"]
        if len(human_agents) < 2:
            return False
        
        # Count votes to end
        end_votes = sum(1 for v in votes.values() if v.get("vote") == "end")
        total_votes = len(votes)
        
        # Need majority (50%+) of agents who voted to agree to end
        # Or if we have votes from majority of all agents, check if majority want to end
        if total_votes >= len(human_agents) * 0.5:  # At least 50% of agents voted
            if end_votes >= total_votes * 0.6:  # 60% of voters want to end
                self.on_event("consensus_reached", {
                    "decision": "end",
                    "end_votes": end_votes,
                    "total_votes": total_votes,
                    "total_agents": len(human_agents),
                })
                return True
        
        # Unanimous agreement (all voters want to end)
        if total_votes >= len(human_agents) * 0.8 and end_votes == total_votes:
            self.on_event("consensus_reached", {
                "decision": "end",
                "end_votes": end_votes,
                "total_votes": total_votes,
                "total_agents": len(human_agents),
            })
            return True
        
        return False
    
    def _compute_step_metrics(self) -> dict[str, Any]:
        """Compute metrics for the current step"""
        total_health = 0
        total_stress = 0
        human_count = 0
        
        for agent in self.agents.values():
            if agent.role == "human":
                human_count += 1
                # Convert to float/int in case they're stored as strings
                health = agent.dynamic_state.get("health", 10)
                stress = agent.dynamic_state.get("stress_level", 5)
                try:
                    total_health += float(health) if health else 10
                    total_stress += float(stress) if stress else 5
                except (ValueError, TypeError):
                    total_health += 10
                    total_stress += 5
        
        return {
            "avg_health": total_health / max(human_count, 1),
            "avg_stress": total_stress / max(human_count, 1),
            "hazard_level": self.world_state.get("hazard_level", 0),
            "message_count": len(self.message_bus._message_history),
            "active_conversations": len(self.conversation_manager.get_all_active_conversations()),
        }
    
    def start_explicit_conversation(
        self,
        initiator_id: str,
        target_agent_ids: list[str],
    ) -> str:
        """Start an explicit conversation between specific agents"""
        initiator_location = self._agent_locations.get(initiator_id)
        return self.conversation_manager.start_explicit_conversation(
            initiator_id, target_agent_ids, initiator_location
        )
    
    def get_agents_at_location(self, location: str) -> list[str]:
        """Get all agent IDs at a specific location"""
        return [
            agent_id
            for agent_id, loc in self._agent_locations.items()
            if loc == location
        ]
    
    async def pause(self) -> None:
        """Pause the simulation"""
        if self.state == SimulationState.RUNNING:
            self._pause_requested = True
    
    async def resume(self) -> None:
        """Resume a paused simulation"""
        if self.state == SimulationState.PAUSED:
            await self.start()
    
    async def stop(self) -> None:
        """Stop the simulation"""
        self._stop_requested = True
        
        run = await self.db.get(Run, self.run_id)
        if run:
            run.status = RunStatus.CANCELLED
            run.completed_at = datetime.utcnow()
            await self.db.commit()
        
        self.state = SimulationState.IDLE
        self.on_event("run_stopped", {"step": self.current_step})
    
    async def step_once(self) -> None:
        """Execute a single step (manual stepping)"""
        if self.state in (SimulationState.IDLE, SimulationState.PAUSED):
            await self._execute_step()
    
    async def _complete_run(self) -> None:
        """Complete the run and trigger evaluation"""
        self.state = SimulationState.COMPLETING
        
        # Run evaluation
        evaluator = EvaluationAgent()
        
        run_summary = {
            "total_steps": self.current_step,
            "hazard_level": self.world_state.get("hazard_level", 0),
            "outcome": "completed",
            "agents_summary": {},
        }
        
        for agent_id, agent in self.agents.items():
            run_summary["agents_summary"][agent.name] = {
                **agent.dynamic_state,
                "action_count": len([
                    m for m in agent.memory if m.get("type") == "action"
                ]),
                "message_count": len([
                    m for m in agent.memory if m.get("type") == "message"
                ]),
            }
        
        all_messages = self.message_bus.get_history()
        
        try:
            evaluation = await evaluator.evaluate_run(run_summary, all_messages)
        except Exception as e:
            evaluation = {"error": str(e)}
        
        # Update run in DB
        run = await self.db.get(Run, self.run_id)
        if run:
            run.status = RunStatus.COMPLETED
            run.completed_at = datetime.utcnow()
            run.metrics = self._compute_step_metrics()
            run.evaluation = evaluation
            await self.db.commit()
        
        self.state = SimulationState.IDLE
        self.on_event("run_completed", {
            "step": self.current_step,
            "evaluation": evaluation,
        })
